
                MATCH (u:User)-[r:LOGON_TO]->(dc:DomainController)
                RETURN u.username, 
                       r.logon_time.hour as hour,
                       count(*) as logon_count
                ORDER BY logon_count DESC
            