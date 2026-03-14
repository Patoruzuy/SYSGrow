import bcrypt
import logging

class UserAuthManager:
    """
    Manages user authentication, including password hashing and verification.
    """

    def __init__(self, database_manager):
        """
        Initializes the AuthenticationManager with a reference to the DatabaseManager.

        Args:
            database_manager (DatabaseManager): An instance of your DatabaseManager class.
        """
        self.database_manager = database_manager

    def hash_password(self, password):
        """
        Hashes the provided password using bcrypt.

        Args:
            password (str): The plain-text password.

        Returns:
            str: The hashed password.
        """
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed_password.decode('utf-8')

    def check_password(self, stored_password, provided_password):
        """
        Verifies if the provided password matches the stored hashed password.

        Args:
            stored_password (str): The hashed password stored in the database.
            provided_password (str): The plain-text password provided by the user.

        Returns:
            bool: True if the passwords match, False otherwise.
        """
        return bcrypt.checkpw(provided_password.encode('utf-8'), stored_password.encode('utf-8'))

    def register_user(self, username, password):
        """
        Registers a new user by hashing their password and storing it in the database.

        Args:
            username (str): The username of the new user.
            password (str): The plain-text password provided by the user.
        """
        password_hash = self.hash_password(password)
        try:
            self.database_manager.insert_user(username, password_hash)
            logging.info(f"User '{username}' registered successfully.")
            return True
        except Exception as e:
            logging.error(f"Error registering user '{username}': {e}")
            return False

    def authenticate_user(self, username, password):
        """
        Authenticates a user by comparing the provided password with the stored hashed password.

        Args:
            username (str): The username of the user.
            password (str): The plain-text password provided by the user.

        Returns:
            bool: True if authentication is successful, False otherwise.
        """
        user = self.database_manager.get_user_by_username(username)
        if user:
            stored_password = user['password_hash']
            if self.check_password(stored_password, password):
                logging.info(f"User '{username}' authenticated successfully.")
                return True
        logging.warning(f"Authentication failed for user '{username}'.")
        return False