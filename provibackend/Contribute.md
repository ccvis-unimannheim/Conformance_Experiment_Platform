# Contribute to the project

## Requirements

- Python 3.12
- Install requirements.txt
- Get .env file from maintainer in order to have correct access to all data


## Known issues

- Its important to keep in mind that due to the use of docker mount, sometimes there are old versions of code in the
docker container instead of the currently developed code. Therefore, when encountering these issues
please delete the container and the volume and re-deploy the docker-compose file.

- When developing locally the nginx is not working due to the fact that its local and not on the server where the dns
would be as expected. This leads to certain issues:
   - Cookies are not being set correctly. The use the secure attribute which can not be used
   - Often the database is empty. A user can then not be authenticated as long as there is not at least one active
   dataset.
   - 
