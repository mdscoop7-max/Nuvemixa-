BEGIN;

CREATE SCHEMA nuvemixa_auth;

CREATE TABLE nuvemixa_auth.state (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    required boolean NOT NULL DEFAULT true CHECK (required),
    ciphertext bytea NOT NULL CHECK (octet_length(ciphertext) > 0)
);

CREATE TABLE nuvemixa_auth.replay (
    step bigint PRIMARY KEY CHECK (step >= 0)
);

CREATE TABLE nuvemixa_auth.attempts (
    ticket text PRIMARY KEY,
    scope text NOT NULL CHECK (scope IN ('password', '2fa')),
    tag bytea NOT NULL CHECK (octet_length(tag) = 32),
    occurred_at double precision NOT NULL,
    failed boolean NOT NULL DEFAULT false
);

CREATE INDEX attempts_lookup ON nuvemixa_auth.attempts (scope, tag, occurred_at);
CREATE INDEX attempts_expiry ON nuvemixa_auth.attempts (occurred_at);

REVOKE ALL ON SCHEMA nuvemixa_auth FROM PUBLIC;
COMMIT;
