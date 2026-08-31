# MySQL schema bootstrap

`001-schema.sql` is idempotent and is mounted into the official MySQL image for a fresh single-host installation. For VM or Kubernetes deployments, run it once with a migration identity before starting application replicas:

```bash
mysql --protocol=TCP --host=mysql.internal --user=duke_migrator --password duke < deploy/mysql/001-schema.sql
```

After bootstrap, give the runtime identity only `SELECT`, `INSERT`, `UPDATE` and `DELETE` on the `duke` schema. Keep the migration identity outside the application secret and back up the database before applying future numbered migrations.
