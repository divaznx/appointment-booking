CREATE OR REPLACE FUNCTION public.cancel_slot_locked(
    p_appointment_id bigint,
    p_user_id uuid,
    p_as_staff boolean DEFAULT false
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_appt public.appointments%ROWTYPE;
BEGIN
    SELECT * INTO v_appt FROM public.appointments WHERE id = p_appointment_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Appointment not found' USING ERRCODE = 'P0002';
    END IF;
    IF v_appt.status <> 'booked' THEN
        RAISE EXCEPTION 'Appointment not found or already cancelled' USING ERRCODE = 'P0001';
    END IF;
    IF NOT p_as_staff AND v_appt.user_id IS DISTINCT FROM p_user_id THEN
        RAISE EXCEPTION 'Forbidden' USING ERRCODE = '42501';
    END IF;

    UPDATE public.appointments
    SET status = 'cancelled', cancelled_at = now()
    WHERE id = p_appointment_id
    RETURNING * INTO v_appt;

    UPDATE public.slots
    SET status = 'available',
        booked_count = GREATEST(COALESCE(booked_count, 1) - 1, 0),
        held_until = NULL,
        held_by = NULL
    WHERE id = v_appt.slot_id;

    INSERT INTO public.outbox_jobs (job_type, payload)
    VALUES (
        'appointment.cancelled',
        jsonb_build_object('appointment_id', v_appt.id, 'user_id', v_appt.user_id)
    );

    INSERT INTO public.audit_log (tenant_id, actor_id, action, entity_type, entity_id, metadata)
    VALUES (
        v_appt.tenant_id, p_user_id, 'appointment.cancelled', 'appointment', v_appt.id::text, '{}'::jsonb
    );

    RETURN to_jsonb(v_appt);
END;
$$;
