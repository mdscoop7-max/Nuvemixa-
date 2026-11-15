BEGIN;

-- Existing active records remain unchanged. Applying this migration alone
-- does not authorize enrollment for a missing record.
ALTER TABLE nuvemixa_auth.state
    ALTER COLUMN ciphertext DROP NOT NULL,
    DROP CONSTRAINT state_required_check,
    ADD CONSTRAINT state_enrollment_shape CHECK (required = (ciphertext IS NOT NULL)),
    ADD COLUMN pending bytea,
    ADD COLUMN pending_until timestamptz,
    ADD CONSTRAINT state_pending_shape CHECK (
        (pending IS NULL) = (pending_until IS NULL) AND
        (NOT required OR pending IS NULL)
    );

COMMIT;

-- Only if an authorized operator has established that there is no prior
-- enrollment to recover, explicitly initialize a new enrollment separately:
-- INSERT INTO nuvemixa_auth.state (required) VALUES (false);
