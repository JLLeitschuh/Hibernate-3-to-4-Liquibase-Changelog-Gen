# Hibernate-3-to-4-Liquibase-Changelog-Gen
A simple generator for creating a liquibase changelog for migrating from Hibernate 3 to Hibernate 4.

This allows you to take a base liquibase changeset for your branch and diff it against your changelog history.
This automatically generates the required drops and adds to migrate your database.

This may not work out of the box for your particular company or use case but this solved it for me.

### Usage

Place this script in the directory you keep your changelog `.xml` files.
You can run the script with the `-h` flags to see the help and the various input arguments.
