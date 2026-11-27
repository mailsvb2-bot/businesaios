-- Standalone UIII database only. Never apply to the BA database.
-- Migration role owns schema/tables. Runtime must be a separate non-owner,
-- non-superuser, NOBYPASSRLS role. Grants are an operator decision.
BEGIN;
CREATE SCHEMA IF NOT EXISTS uiii;
CREATE TABLE uiii.evidence (
 tenant text NOT NULL, business text NOT NULL, controller text NOT NULL, purpose text NOT NULL,
 evidence_id text NOT NULL, revision bigint NOT NULL CHECK(revision>0),
 source_record text NOT NULL CHECK(length(source_record)>0), upstream_origin text NOT NULL CHECK(length(upstream_origin)>0),
 rule_version text NOT NULL CHECK(length(rule_version)>0),
 valid_from timestamptz NOT NULL, valid_until timestamptz NOT NULL CHECK(valid_until>valid_from),
 observed_at timestamptz, recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 retracted_at timestamptz, payload jsonb NOT NULL, fingerprint text NOT NULL,
 PRIMARY KEY(tenant,business,controller,purpose,evidence_id),
 CHECK(tenant<>'' AND business<>'' AND controller<>'' AND purpose<>''),
 CHECK(retracted_at IS NULL OR retracted_at>=recorded_at)
);
CREATE TABLE uiii.evidence_parent (
 tenant text NOT NULL, business text NOT NULL, controller text NOT NULL, purpose text NOT NULL,
 child text NOT NULL, parent text NOT NULL,
 PRIMARY KEY(tenant,business,controller,purpose,child,parent), CHECK(child<>parent),
 FOREIGN KEY(tenant,business,controller,purpose,child) REFERENCES uiii.evidence ON DELETE CASCADE,
 FOREIGN KEY(tenant,business,controller,purpose,parent) REFERENCES uiii.evidence
);
CREATE TABLE uiii.delivery (
 tenant text NOT NULL, business text NOT NULL, controller text NOT NULL, purpose text NOT NULL,
 delivery_id text NOT NULL, recipient text NOT NULL, signal_id text NOT NULL, revision bigint NOT NULL CHECK(revision>0),
 kind text NOT NULL CHECK(kind IN ('signal','retraction')), payload jsonb NOT NULL,
 state text NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','leased','received','applied','failed')),
 attempts integer NOT NULL DEFAULT 0 CHECK(attempts>=0), next_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 lease_owner text, lease_until timestamptz, error_code text,
 PRIMARY KEY(tenant,business,controller,purpose,delivery_id),
 UNIQUE(tenant,business,controller,purpose,recipient,signal_id,revision,kind)
);
CREATE INDEX uiii_delivery_due ON uiii.delivery(state,next_at,lease_until);
CREATE TABLE uiii.budget (
 tenant text NOT NULL, business text NOT NULL, controller text NOT NULL, purpose text NOT NULL,
 budget_key text NOT NULL, currency text NOT NULL CHECK(currency~'^[A-Z]{3}$'),
 cap_minor bigint NOT NULL CHECK(cap_minor>=0), used_minor bigint NOT NULL DEFAULT 0 CHECK(used_minor>=0),
 PRIMARY KEY(tenant,business,controller,purpose,budget_key), CHECK(used_minor<=cap_minor)
);
CREATE TABLE uiii.reservation (
 tenant text NOT NULL, business text NOT NULL, controller text NOT NULL, purpose text NOT NULL,
 budget_key text NOT NULL, operation_id text NOT NULL, maximum_minor bigint NOT NULL CHECK(maximum_minor>=0),
 committed_minor bigint CHECK(committed_minor>=0 AND committed_minor<=maximum_minor),
 PRIMARY KEY(tenant,business,controller,purpose,budget_key,operation_id),
 FOREIGN KEY(tenant,business,controller,purpose,budget_key) REFERENCES uiii.budget
);
CREATE TABLE uiii.privacy_request (
 tenant text NOT NULL, business text NOT NULL, controller text NOT NULL, purpose text NOT NULL,
 request_id text NOT NULL, subject_token text NOT NULL, requested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 stage text NOT NULL CHECK(stage IN ('restricted','purging','awaiting_recipients','complete','exception')),
 pending_stores text[] NOT NULL, pending_recipients text[] NOT NULL,
 PRIMARY KEY(tenant,business,controller,purpose,request_id),
 CHECK(stage<>'complete' OR (cardinality(pending_stores)=0 AND cardinality(pending_recipients)=0))
);
-- All four dimensions must be set via authorized SET LOCAL in the transaction.
DO $$ DECLARE tab text; BEGIN
 FOREACH tab IN ARRAY ARRAY['evidence','evidence_parent','delivery','budget','reservation','privacy_request'] LOOP
  EXECUTE format('ALTER TABLE uiii.%I ENABLE ROW LEVEL SECURITY',tab);
  EXECUTE format('ALTER TABLE uiii.%I FORCE ROW LEVEL SECURITY',tab);
  EXECUTE format('CREATE POLICY scoped_access ON uiii.%I USING (
    tenant=current_setting(''uiii.tenant'',true) AND business=current_setting(''uiii.business'',true)
    AND controller=current_setting(''uiii.controller'',true) AND purpose=current_setting(''uiii.purpose'',true))
    WITH CHECK (tenant=current_setting(''uiii.tenant'',true) AND business=current_setting(''uiii.business'',true)
    AND controller=current_setting(''uiii.controller'',true) AND purpose=current_setting(''uiii.purpose'',true))',tab);
 END LOOP;
END $$;
CREATE FUNCTION uiii.claim_deliveries(worker text, batch integer, lease interval)
RETURNS SETOF uiii.delivery LANGUAGE plpgsql SECURITY INVOKER AS $$
BEGIN
 IF worker IS NULL OR worker='' OR batch IS NULL OR lease IS NULL OR batch NOT BETWEEN 1 AND 100 OR lease<=interval '0' OR lease>interval '10 minutes' THEN
  RAISE EXCEPTION 'invalid lease request';
 END IF;
 RETURN QUERY WITH selected AS (
  SELECT tenant,business,controller,purpose,delivery_id FROM uiii.delivery
  WHERE next_at<=clock_timestamp() AND (state='pending' OR (state='leased' AND lease_until<clock_timestamp()))
  ORDER BY next_at,delivery_id FOR UPDATE SKIP LOCKED LIMIT batch
 ) UPDATE uiii.delivery d SET state='leased',attempts=d.attempts+1,lease_owner=worker,lease_until=clock_timestamp()+lease
 FROM selected s WHERE (d.tenant,d.business,d.controller,d.purpose,d.delivery_id)=
 (s.tenant,s.business,s.controller,s.purpose,s.delivery_id) RETURNING d.*;
END $$;
-- The locked budget row is the concurrency serialization boundary.
CREATE FUNCTION uiii.reserve(key_ text, operation_ text, maximum_ bigint) RETURNS boolean
LANGUAGE plpgsql SECURITY INVOKER AS $$
DECLARE b uiii.budget; r uiii.reservation;
BEGIN
 IF operation_ IS NULL OR operation_='' OR maximum_ IS NULL OR maximum_<0 THEN RAISE EXCEPTION 'invalid reservation'; END IF;
 SELECT * INTO STRICT b FROM uiii.budget WHERE budget_key=key_ FOR UPDATE;
 SELECT * INTO r FROM uiii.reservation WHERE budget_key=key_ AND operation_id=operation_;
 IF FOUND THEN
  IF r.maximum_minor<>maximum_ THEN RAISE EXCEPTION 'reservation conflict'; END IF;
  RETURN false;
 END IF;
 IF maximum_>b.cap_minor-b.used_minor THEN RAISE EXCEPTION 'budget exceeded'; END IF;
 INSERT INTO uiii.reservation VALUES(b.tenant,b.business,b.controller,b.purpose,key_,operation_,maximum_,NULL);
 UPDATE uiii.budget SET used_minor=used_minor+maximum_ WHERE budget_key=key_;
 RETURN true;
END $$;
CREATE FUNCTION uiii.commit_reservation(key_ text, operation_ text, amount_ bigint) RETURNS void
LANGUAGE plpgsql SECURITY INVOKER AS $$
DECLARE b uiii.budget; r uiii.reservation;
BEGIN
 SELECT * INTO STRICT b FROM uiii.budget WHERE budget_key=key_ FOR UPDATE;
 SELECT * INTO STRICT r FROM uiii.reservation WHERE budget_key=key_ AND operation_id=operation_ FOR UPDATE;
 IF amount_ IS NULL OR amount_<0 OR amount_>r.maximum_minor THEN RAISE EXCEPTION 'commit out of bounds'; END IF;
 IF r.committed_minor IS NOT NULL THEN
  IF r.committed_minor<>amount_ THEN RAISE EXCEPTION 'commit conflict'; END IF;
  RETURN;
 END IF;
 UPDATE uiii.reservation SET committed_minor=amount_ WHERE budget_key=key_ AND operation_id=operation_;
 UPDATE uiii.budget SET used_minor=used_minor-(r.maximum_minor-amount_) WHERE budget_key=key_;
END $$;
-- No implicit public grant and no SECURITY DEFINER privileges.
REVOKE ALL ON ALL TABLES IN SCHEMA uiii FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA uiii FROM PUBLIC;
COMMIT;
