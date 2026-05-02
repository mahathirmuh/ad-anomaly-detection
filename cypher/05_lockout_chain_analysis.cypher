
                MATCH (u:User)-[r:LOCKED_OUT]->(dc:DomainController)
                RETURN u.username, count(r) as lockout_count, 
                       collect(DISTINCT dc.name) as locked_on_dcs
                ORDER BY lockout_count DESC
                LIMIT 50
            