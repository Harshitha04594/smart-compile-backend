# Use an official OpenJDK runtime as a parent image
FROM openjdk:17-jdk-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Define a command to compile and run the Java program
CMD ["sh", "-c", "javac Main.java && java Main"]
