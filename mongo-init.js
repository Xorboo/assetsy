print('Starting MongoDB initialization script...');

print('Switching to database:', process.env.MONGO_INITDB_DATABASE);
db = db.getSiblingDB(process.env.MONGO_INITDB_DATABASE);

print('Creating application user...');
db.createUser({
  user: process.env.MONGO_APP_USERNAME,
  pwd: process.env.MONGO_APP_PASSWORD,
  roles: [
    {
      role: 'readWrite',
      db: process.env.MONGO_INITDB_DATABASE,
    },
  ],
});

print('Creating collections...');
db.createCollection('scraped_data', { capped: false });
db.createCollection('telegram_users', { capped: false });
print('MongoDB initialization complete');
