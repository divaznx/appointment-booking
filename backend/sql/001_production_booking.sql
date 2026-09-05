-- Production booking schema (run in Supabase SQL editor).
-- Additive: existing slots/appointments keep working.

CREATE TABLE IF NOT EXISTS public.tenants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.locations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    name text NOT NULL,
    timezone text NOT NULL DEFAULT 'UTC',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.resources (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    location_id uuid REFERENCES public.locations(id) ON DELETE SET NULL,
    name text NOT NULL,
    capacity integer NOT NULL DEFAULT 1 CHECK (capacity >= 1),
    booking_model text NOT NULL DEFAULT 'single' CHECK (booking_model IN ('single', 'capacity')),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.profiles (
    id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    tenant_id uuid REFERENCES public.tenants(id) ON DELETE SET NULL,
    role text NOT NULL DEFAULT 'customer' CHECK (role IN ('customer', 'staff', 'admin')),
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.slots
    ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES public.tenants(id),
    ADD COLUMN IF NOT EXISTS location_id uuid REFERENCES public.locations(id),
    ADD COLUMN IF NOT EXISTS resource_id uuid REFERENCES public.resources(id),
    ADD COLUMN IF NOT EXISTS timezone text DEFAULT 'UTC',
    ADD COLUMN IF NOT EXISTS capacity integer DEFAULT 1,
    ADD COLUMN IF NOT EXISTS booked_count integer DEFAULT 0,
    ADD COLUMN IF NOT EXISTS booking_model text DEFAULT 'single',
    ADD COLUMN IF NOT EXISTS held_until timestamptz,
    ADD COLUMN IF NOT EXISTS held_by uuid;

ALTER TABLE public.appointments
    ADD COLUMN IF NOT EXISTS tenant_id uuid REFERENCES public.tenants(id),
    ADD COLUMN IF NOT EXISTS location_id uuid REFERENCES public.locations(id),
    ADD COLUMN IF NOT EXISTS idempotency_key text,
    ADD COLUMN IF NOT EXISTS hold_expires_at timestamptz;

CREATE UNIQUE INDEX IF NOT EXISTS appointments_idempotency_key_uidx
    ON public.appointments (idempotency_key)
    WHERE idempotency_key IS NOT NULL;

-- One active booking per slot for single-resource model
CREATE UNIQUE INDEX IF NOT EXISTS appointments_one_active_per_slot
    ON public.appointments (slot_id)
    WHERE status IN ('held', 'booked');

CREATE TABLE IF NOT EXISTS public.idempotency_keys (
    key text PRIMARY KEY,
    user_id text NOT NULL,
    method text NOT NULL,
    path text NOT NULL,
    request_hash text NOT NULL,
    status_code integer NOT NULL,
    response jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.audit_log (
    id bigserial PRIMARY KEY,
    tenant_id uuid,
    actor_id uuid,
    action text NOT NULL,
    entity_type text NOT NULL,
    entity_id text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_log_actor_idx ON public.audit_log (actor_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.outbox_jobs (
    id bigserial PRIMARY KEY,
    job_type text NOT NULL,
    payload jsonb NOT NULL,
    available_at timestamptz NOT NULL DEFAULT now(),
    processed_at timestamptz,
    attempts integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.webhook_endpoints (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid REFERENCES public.tenants(id) ON DELETE CASCADE,
    url text NOT NULL,
    secret text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.recurring_series (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid REFERENCES public.tenants(id),
    location_id uuid REFERENCES public.locations(id),
    resource_id uuid REFERENCES public.resources(id),
    rrule text NOT NULL,
    dtstart timestamptz NOT NULL,
    duration_minutes integer NOT NULL CHECK (duration_minutes > 0),
    timezone text NOT NULL DEFAULT 'UTC',
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.recurring_occurrences (
    id bigserial PRIMARY KEY,
    series_id uuid NOT NULL REFERENCES public.recurring_series(id) ON DELETE CASCADE,
    start_time timestamptz NOT NULL,
    end_time timestamptz NOT NULL,
    slot_id bigint REFERENCES public.slots(id) ON DELETE SET NULL,
    UNIQUE (series_id, start_time)
);

CREATE OR REPLACE FUNCTION public.hold_slot(
    p_slot_id bigint,
    p_user_id uuid,
    p_hold_seconds integer DEFAULT 120
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_slot public.slots%ROWTYPE;
BEGIN
    SELECT * INTO v_slot FROM public.slots WHERE id = p_slot_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Slot is not available' USING ERRCODE = 'P0001';
    END IF;

    IF v_slot.held_until IS NOT NULL AND v_slot.held_until < now() THEN
        UPDATE public.slots
        SET held_until = NULL, held_by = NULL, status = 'available'
        WHERE id = p_slot_id AND status = 'held';
        v_slot.status := 'available';
        v_slot.held_by := NULL;
    END IF;

    IF v_slot.status = 'held' AND v_slot.held_by IS NOT DISTINCT FROM p_user_id THEN
        UPDATE public.slots
        SET held_until = now() + make_interval(secs => p_hold_seconds)
        WHERE id = p_slot_id
        RETURNING * INTO v_slot;
        RETURN to_jsonb(v_slot);
    END IF;

    IF v_slot.status <> 'available' THEN
        RAISE EXCEPTION 'Slot is not available' USING ERRCODE = 'P0001';
    END IF;

    UPDATE public.slots
    SET status = 'held',
        held_by = p_user_id,
        held_until = now() + make_interval(secs => p_hold_seconds)
    WHERE id = p_slot_id
    RETURNING * INTO v_slot;

    RETURN to_jsonb(v_slot);
END;
$$;

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
        RAISE EXCEPTION 'Appointment not found or already cancelled' USING ERRCODE = 'P0001';
    END IF;
    IF v_appt.status <> 'booked' THEN
        RAISE EXCEPTION 'Appointment not found or already cancelled' USING ERRCODE = 'P0001';
    END IF;
    IF NOT p_as_staff AND v_appt.user_id IS DISTINCT FROM p_user_id THEN
        RAISE EXCEPTION 'Appointment not found or already cancelled' USING ERRCODE = 'P0001';
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

GRANT EXECUTE ON FUNCTION public.hold_slot(bigint, uuid, integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.book_slot_locked(bigint, uuid, text) TO service_role;
GRANT EXECUTE ON FUNCTION public.cancel_slot_locked(bigint, uuid, boolean) TO service_role;
