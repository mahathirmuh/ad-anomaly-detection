
                MATCH (u:User)-[:ADDED_TO_GROUP]->(g:Group)
                WHERE g.group_scope = 'Global' OR g.group_type = 'Security'
                RETURN u.username, g.groupname, g.group_scope
                ORDER BY g.groupname
            