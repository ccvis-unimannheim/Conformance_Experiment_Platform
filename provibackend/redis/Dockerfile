# Use the official Redis image as the base image
FROM redis:8-alpine

# Copy the redis.conf file to the appropriate directory in the container
COPY redis.conf /usr/local/etc/redis/redis.conf

# Set the command to run Redis with the custom configuration file
CMD ["redis-server", "/usr/local/etc/redis/redis.conf"]