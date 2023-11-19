# MongoDB Interface

Interface for MongoDB to be used with the [MongoDB](https://www.mongodb.com/) project. You can either use a local,
self-hosted, or MongoDB instance or a MongoDB Atlas instance. To use this interface, set up these environment variables:

```bash
UP_MONGO_USER=<username>
UP_MONGO_PASSWORD=<password>
UP_MONGO_DOMAIN=<domain>
UP_MONGO_DATABASE=<database>
PROJECT_PATH=<path to the project folder>
```

Install python requirements:

```bash
pip install -r requirements.txt
```

## Usage

```python
import mongo.mongo

db = mongo.get_database()
```