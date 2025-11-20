# Vercel Deployment Setup Guide

## Before Deploying

Since `IoS_logins.py` is in `.gitignore` and won't be committed to git, you need to set up environment variables in Vercel.

## Step 1: Push to Git

1. Make sure all your changes are committed:
   ```bash
   git add .
   git commit -m "Configure for Vercel deployment"
   git push
   ```

## Step 2: Connect to Vercel

1. Go to [vercel.com](https://vercel.com) and sign in
2. Click "Add New Project"
3. Import your Git repository
4. Vercel will auto-detect the Python/Flask setup

## Step 3: Add Environment Variables

In your Vercel project settings, go to **Settings → Environment Variables** and add:

### Required Credentials:

**Tapo Devices:**
- `TAPO_EMAIL` - Your Tapo account email
- `TAPO_PASSWORD` - Your Tapo account password

**Meross Devices:**
- `MEROSS_EMAIL` - Your Meross account email
- `MEROSS_PASSWORD` - Your Meross account password

**Arlec/Tuya Devices:**
- `TUYA_ACCESS_ID` - Tuya API access ID
- `TUYA_ACCESS_SECRET` - Tuya API access secret
- `TUYA_API_REGION` - Tuya API region (e.g., `us`, `eu`, `cn`)

**MongoDB (if using):**
- `MONGO_USERNAME` - MongoDB username
- `MONGO_PASSWORD` - MongoDB password
- `MONGO_URI` - MongoDB connection URI
- `MONGO_DB_NAME` - MongoDB database name
- `MONGO_COLLECTION_NAME` - MongoDB collection name

### Optional Device Configuration:

**Known Devices (JSON format):**
- `KNOWN_DEVICES` - JSON string with device IPs, e.g.:
  ```json
  {"tapo_wine_fridge": "192.168.86.37"}
  ```

**Matter Devices (JSON format):**
- `MATTER_DEVICES` - JSON string with Matter device configs, e.g.:
  ```json
  {
    "device_id_1": {
      "ip": "192.168.1.100",
      "port": 5540,
      "name": "Device Name"
    }
  }
  ```

## Step 4: Deploy

After adding environment variables, Vercel will automatically redeploy. You can also trigger a manual redeploy from the dashboard.

## Testing

Once deployed, visit your Vercel URL (e.g., `https://your-project.vercel.app`) to test the website.

## Notes

- Environment variables are encrypted and secure in Vercel
- You can set different values for Production, Preview, and Development environments
- The app will work locally with `IoS_logins.py` and on Vercel with environment variables
- If you don't use certain device types, you can leave those environment variables empty

