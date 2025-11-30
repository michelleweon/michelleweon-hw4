# Deployment Guide for Vercel

## Step 1: Database Regeneration ✅ COMPLETE

Your database has been regenerated with the correct schema:
- ✅ `zip_county` table has `zip` column (not `col__zip`)
- ✅ `county_health_rankings` table has correct schema
- ✅ 54,553 ZIP records
- ✅ 303,864 health ranking records

## Step 2: Commit Your Changes

```bash
# Add the fixed files
git add csv_to_sqlite.py api/index.py link.txt

# Commit
git commit -m "Fix autograder issues: add POST endpoint, fix column names, handle BOM"

# Push to GitHub
git push
```

## Step 3: Deploy to Vercel

### Option A: Automatic Deployment (Recommended)
If your GitHub repo is connected to Vercel, it will automatically deploy when you push:

1. **Push your changes** (see Step 2)
2. **Check Vercel Dashboard**: Go to https://vercel.com/dashboard
3. **Wait for deployment** to complete (usually 1-2 minutes)
4. **Test your endpoint**:
   ```bash
   curl -X POST https://michelleweon-hw4.vercel.app/county_data \
     -H "Content-Type: application/json" \
     -d '{"zip":"02138","measure_name":"Adult obesity"}'
   ```

### Option B: Manual Deployment via Vercel CLI

If you have Vercel CLI installed:

```bash
# Install Vercel CLI (if not already installed)
npm i -g vercel

# Deploy
vercel --prod
```

### Option C: Deploy via Vercel Dashboard

1. Go to https://vercel.com/dashboard
2. Find your project `michelleweon-hw4`
3. Click "Redeploy" or trigger a new deployment
4. Wait for deployment to complete

## Step 4: Verify Deployment

After deployment, test your endpoint:

```bash
# Test 1: Valid request
curl -X POST https://michelleweon-hw4.vercel.app/county_data \
  -H "Content-Type: application/json" \
  -d '{"zip":"02138","measure_name":"Adult obesity"}'

# Test 2: Teapot error (should return 418)
curl -X POST https://michelleweon-hw4.vercel.app/county_data \
  -H "Content-Type: application/json" \
  -d '{"zip":"02138","measure_name":"Adult obesity","coffee":"teapot"}'

# Test 3: Missing zip (should return 400)
curl -X POST https://michelleweon-hw4.vercel.app/county_data \
  -H "Content-Type: application/json" \
  -d '{"measure_name":"Adult obesity"}'

# Test 4: Invalid ZIP (should return 404)
curl -X POST https://michelleweon-hw4.vercel.app/county_data \
  -H "Content-Type: application/json" \
  -d '{"zip":"99999","measure_name":"Adult obesity"}'
```

## Important Notes

1. **Database File**: Make sure `data.db` is committed to your repository (Vercel needs it)
2. **Link.txt**: Should contain: `https://michelleweon-hw4.vercel.app/county_data`
3. **Vercel Configuration**: Your `vercel.json` is already set up correctly

## Troubleshooting

### If deployment fails:
- Check Vercel logs in the dashboard
- Make sure all dependencies are in `requirements.txt`
- Verify `data.db` is in the repository

### If API returns 500 errors:
- Check Vercel function logs
- Verify database path is correct in `api/index.py`
- Make sure `data.db` is accessible

### If endpoint returns 405:
- Verify the route is `/county_data` (not `/api/county_data`)
- Check that `methods=['POST']` is set in the route decorator
