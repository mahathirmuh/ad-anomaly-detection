
                MATCH (u:User)-[r:LOGON_TO]->(dc:DomainController)
                RETURN u.username, r.logon_time, r.event_type, dc.name
                ORDER BY r.logon_time DESC
                LIMIT 100
            