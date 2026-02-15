# Use a slim version of Ubuntu for a lightweight image
FROM gcc:latest

# Set the working directory
WORKDIR /app

# Copy the source code into the container
COPY . /app

# Define a command to compile and run the C program
CMD ["sh", "-c", "gcc main.c -o main && ./main"]
