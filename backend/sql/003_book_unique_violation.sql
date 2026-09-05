-- Re-run in Supabase SQL editor if 001 was already applied.
-- Maps unique-index races (and duplicate idempotency keys) to P0001 instead of 23505.

CREATE OR REPLACE FUNCTION public.book_slot_locked(
    p_slot_id bigint,
    p_user_id uuid,
    p_idempotency_key text DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_slot public.slots%ROWTYPE;
    v_appt public.appointments%ROWTYPE;
    v_booked integer;
BEGIN
    IF p_idempotency_key IS NOT NULL THEN
        SELECT * INTO v_appt
        FROM public.appointments
        WHERE idempotency_key = p_idempotency_key;
        IF FOUND THEN
            RETURN to_jsonb(v_appt);
        END IF;
    END IF;

    SELECT * INTO v_slot FROM public.slots WHERE id = p_slot_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Slot is not available' USING ERRCODE = 'P0001';
    END IF;

    IF v_slot.start_time <= now() THEN
        RAISE EXCEPTION 'Slot is not available' USING ERRCODE = 'P0001';
    END IF;

    IF v_slot.held_until IS NOT NULL AND v_slot.held_until < now() THEN
        UPDATE public.slots
        SET held_until = NULL, held_by = NULL,
            status = CASE WHEN status = 'held' THEN 'available' ELSE status END
        WHERE id = p_slot_id;
        SELECT * INTO v_slot FROM public.slots WHERE id = p_slot_id FOR UPDATE;
    END IF;

    IF v_slot.status = 'held' AND v_slot.held_by IS DISTINCT FROM p_user_id THEN
        RAISE EXCEPTION 'Slot is not available' USING ERRCODE = 'P0001';
    END IF;

    BEGIN
        IF COALESCE(v_slot.booking_model, 'single') = 'capacity' THEN
            SELECT count(*) INTO v_booked
            FROM public.appointments
            WHERE slot_id = p_slot_id AND status IN ('held', 'booked');
            IF v_booked >= COALESCE(v_slot.capacity, 1) THEN
                RAISE EXCEPTION 'Slot is not available' USING ERRCODE = 'P0001';
            END IF;
            INSERT INTO public.appointments (slot_id, user_id, status, idempotency_key, tenant_id, location_id)
            VALUES (p_slot_id, p_user_id, 'booked', p_idempotency_key, v_slot.tenant_id, v_slot.location_id)
            RETURNING * INTO v_appt;
            UPDATE public.slots
            SET booked_count = v_booked + 1,
                status = CASE WHEN v_booked + 1 >= COALESCE(capacity, 1) THEN 'booked' ELSE 'available' END,
                held_until = NULL,
                held_by = NULL
            WHERE id = p_slot_id;
        ELSE
            IF v_slot.status NOT IN ('available', 'held') THEN
                RAISE EXCEPTION 'Slot is not available' USING ERRCODE = 'P0001';
            END IF;
            INSERT INTO public.appointments (slot_id, user_id, status, idempotency_key, tenant_id, location_id)
            VALUES (p_slot_id, p_user_id, 'booked', p_idempotency_key, v_slot.tenant_id, v_slot.location_id)
            RETURNING * INTO v_appt;
            UPDATE public.slots
            SET status = 'booked', held_until = NULL, held_by = NULL, booked_count = 1
            WHERE id = p_slot_id;
        END IF;
    EXCEPTION WHEN unique_violation THEN
        IF p_idempotency_key IS NOT NULL THEN
            SELECT * INTO v_appt
            FROM public.appointments
            WHERE idempotency_key = p_idempotency_key;
            IF FOUND THEN
                RETURN to_jsonb(v_appt);
            END IF;
        END IF;
        RAISE EXCEPTION 'Slot is not available' USING ERRCODE = 'P0001';
    END;

    INSERT INTO public.outbox_jobs (job_type, payload)
    VALUES (
        'appointment.booked',
        jsonb_build_object('appointment_id', v_appt.id, 'user_id', p_user_id, 'slot_id', p_slot_id)
    );

    INSERT INTO public.audit_log (tenant_id, actor_id, action, entity_type, entity_id, metadata)
    VALUES (
        v_slot.tenant_id, p_user_id, 'appointment.booked', 'appointment', v_appt.id::text,
        jsonb_build_object('slot_id', p_slot_id)
    );

    RETURN to_jsonb(v_appt);
END;
$$;
