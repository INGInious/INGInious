from pymongo import MongoClient
from gridfs import GridFS

from inginious.frontend.user_manager import UserManager

def try_mongodb_opts(host="localhost", database_name='INGInious'):
    """ Try MongoDB configuration """
    try:
        mongo_client = MongoClient(host=host)
        # Effective access only occurs when we call a method on the connexion
        mongo_version = str(mongo_client.server_info()['version'])
        print("Found mongodb server running version %s on %s." % (mongo_version, host))
    except Exception as e:
        print("Cannot connect to MongoDB on host %s: %s" % (host, str(e)))
        return None

    try:
        database = mongo_client[database_name]
        # Effective access only occurs when we call a method on the database.
        database.list_collection_names()
    except Exception as e:
        print("Cannot access database %s: %s" % (database_name, str(e)))
        return None

    try:
        # Effective access only occurs when we call a method on the gridfs object.
        GridFS(database).find_one()
    except Exception as e:
        print("Cannot access gridfs %s: %s" % (database_name, str(e)))
        return None

    return database

if __name__ == '__main__':
    username = "superadmin"
    realname = "INGInious superadmin"
    email = "superadmin@inginious.org"
    password = "superadmin"

    print('Initial DB setup.')

    database = try_mongodb_opts('db')

    database.users.insert_one({"username": username,
                               "realname": realname,
                               "email": email,
                               "password": UserManager.hash_password(password),
                               "bindings": {},
                               "language": "en",
                               "code_indentation": "4"})
    print('Superadmin user added!')
