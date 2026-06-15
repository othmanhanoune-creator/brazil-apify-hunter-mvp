create extension if not exists pgcrypto;

create table if not exists leads (
    lead_id text primary key,
    market text not null default 'Brazil',
    name text not null,
    city text,
    state text,
    country text,
    phone text,
    website text,
    email text,
    email_source text,
    email_status text,
    email_confidence text,
    contact_form_url text,
    b2b_score integer,
    gold_split_status text,
    gold_split_reason text,
    source_url text,
    lead_status text not null default 'available',
    assigned_to_email text,
    assigned_to_name text,
    assigned_at timestamptz,
    source_batch text,
    imported_at timestamptz default now(),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists lead_claims (
    claim_id uuid primary key default gen_random_uuid(),
    lead_id text not null references leads(lead_id) on delete cascade,
    user_email text not null,
    user_name text,
    claimed_at timestamptz not null default now(),
    action text not null default 'claimed'
);

create unique index if not exists idx_lead_claims_unique_lead_id on lead_claims(lead_id);
create index if not exists idx_leads_market on leads(market);
create index if not exists idx_leads_status on leads(lead_status);
create index if not exists idx_leads_state on leads(state);

create or replace function claim_lead(
    p_lead_id text,
    p_user_email text,
    p_user_name text
)
returns jsonb
language plpgsql
as $$
declare
    updated_count integer;
begin
    update leads
    set
        lead_status = 'claimed',
        assigned_to_email = p_user_email,
        assigned_to_name = p_user_name,
        assigned_at = now(),
        updated_at = now()
    where lead_id = p_lead_id
      and coalesce(lead_status, 'available') = 'available';

    get diagnostics updated_count = row_count;

    if updated_count = 0 then
        return jsonb_build_object('success', false, 'message', 'Lead already claimed or unavailable');
    end if;

    insert into lead_claims (lead_id, user_email, user_name, claimed_at, action)
    values (p_lead_id, p_user_email, p_user_name, now(), 'claimed')
    on conflict (lead_id) do nothing;

    return jsonb_build_object('success', true, 'message', 'Lead claimed successfully');
exception
    when others then
        return jsonb_build_object('success', false, 'message', SQLERRM);
end;
$$;
