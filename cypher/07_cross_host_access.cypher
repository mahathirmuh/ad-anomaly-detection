
                MATCH (u:User)-[:ACCESSED_FROM]->(h:Host)
                RETURN u.username, count(DISTINCT h) as unique_hosts,
                       collect(DISTINCT h.hostname) as hosts
                ORDER BY unique_hosts DESC
                LIMIT 50
            