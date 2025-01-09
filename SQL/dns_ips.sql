CREATE TABLE dns_ips (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	provider varchar(255) NOT NULL,
	ipv4 _inet NULL,
	ipv6 _inet NULL,
	created_at timestamp DEFAULT now() NOT NULL,
	CONSTRAINT dns_ips_pkey PRIMARY KEY (id)
);

-- INSERT INTO dns_ips (provider,created_at,ipv4,ipv6) VALUES
--     ('Google','2024-09-11 13:51:00.893','{8.8.8.8,8.8.4.4}','{2001:4860:4860::8888,2001:4860:4860::8844}'),
--     ('Quad9','2024-09-11 13:51:00.893','{9.9.9.9,149.112.112.112}','{2620:fe::fe,2620:fe::9}'),
--     ('Cloudflare','2024-09-11 13:51:00.893','{1.1.1.1,1.0.0.1}','{2606:4700:4700::1111,2606:4700:4700::1001}'),
--     ('AdGuard','2024-09-11 13:51:00.893','{94.140.14.14,94.140.15.15}','{2a10:50c0::ad1:ff,2a10:50c0::ad2:ff}'),
--     ('OpenDNS','2024-09-11 13:51:00.893','{208.67.222.222,208.67.220.220}','{2620:119:35::35,2620:119:53::53}'),
--     ('CleanBrowsing','2024-09-11 13:51:00.893','{185.228.168.9,185.228.169.9}','{2a0d:2a00:1::2,2a0d:2a00:2::2}');
