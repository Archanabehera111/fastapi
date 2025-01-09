create table if not exists vulnerabilities (
	id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
	ip_address inet not null,
	cve_id varchar,
    created_at timestamp default now(),
    updated_at timestamp default now(),
	unique (ip_address, cve_id)
)
