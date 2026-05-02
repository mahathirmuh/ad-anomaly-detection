
                MATCH (u:User)-[r:FAILED_LOGON]->(dc:DomainController)
                RETURN u.username, count(r) as failure_count, 
                       collect(DISTINCT r.failure_reason) as reasons
                ORDER BY failure_count DESC
                LIMIT 50
            