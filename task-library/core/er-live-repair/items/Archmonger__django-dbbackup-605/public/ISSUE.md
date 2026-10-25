Error running `pg_dump`, unable to find command
Run  `python manage.py dbbackup`, get error: `[Errno 2] No such file or directory`, traceback:

```
Traceback (most recent call last):
  File "manage.py", line 23, in <module>
    execute_from_command_line(sys.argv)
  File "/usr/lib/python2.7/site-packages/django/core/management/__init__.py", line 364, in execute_from_command_line
    utility.execute()
  File "/usr/lib/python2.7/site-packages/django/core/management/__init__.py", line 356, in execute
    self.fetch_command(subcommand).run_from_argv(self.argv)
  File "/usr/lib/python2.7/site-packages/django/core/management/base.py", line 283, in run_from_argv
    self.execute(*args, **cmd_options)
  File "/usr/lib/python2.7/site-packages/django/core/management/base.py", line 330, in execute
    output = self.handle(*args, **options)
  File "/usr/lib/python2.7/site-packages/dbbackup/utils.py", line 116, in wrapper
    func(*args, **kwargs)
  File "/usr/lib/python2.7/site-packages/dbbackup/management/commands/dbbackup.py", line 61, in handle
    self._save_new_backup(database)
  File "/usr/lib/python2.7/site-packages/dbbackup/management/commands/dbbackup.py", line 74, in _save_new_backup
    outputfile = self.connector.create_dump()
  File "/usr/lib/python2.7/site-packages/dbbackup/db/base.py", line 76, in create_dump
    dump = self._create_dump()
  File "/usr/lib/python2.7/site-packages/dbbackup/db/postgresql.py", line 37, in _create_dump
    stdout, stderr = self.run_command(cmd, env=self.dump_env)
  File "/usr/lib/python2.7/site-packages/dbbackup/db/postgresql.py", line 21, in run_command
    return super(PgDumpConnector, self).run_command(*args, **kwargs)
  File "/usr/lib/python2.7/site-packages/dbbackup/db/base.py", line 150, in run_command
    "Error running: {}\n{}".format(command, str(err)))
dbbackup.db.exceptions.CommandConnectorError: Error running:  pg_dump gdi --host=localhost --port=5432 --username=gdi --no-password --clean

```
Under docker compose.
Django: `1.11.7`
django-dbbackup: `3.2.0`
djangorestframework: `3.7.1`
