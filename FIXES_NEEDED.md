# Fixes Needed for Autograder

## Summary of Issues from Autograder

**Current Score: 21/50**
- Part 1: 11/15 (schema issues)
- Part 2: 10/35 (POST endpoint not working)

## Part 1 Fixes (Schema Issues)

### Issue: Column names being prefixed with `col_` when they shouldn't be
- Expected: `zip`, `field_one`
- Got: `col__zip`, `col__field_one`

### Fix Applied:
- Updated `csv_to_sqlite.py` to only add `col_` prefix if column name starts with a digit
- Headers starting with letters or underscores are preserved as-is

### Action Required:
1. **Regenerate the database** with the fixed script:
   ```bash
   rm data.db
   python3 csv_to_sqlite.py data.db zip_county.csv
   python3 csv_to_sqlite.py data.db county_health_rankings.csv
   ```

2. **Verify schema**:
   ```bash
   sqlite3 data.db ".schema zip_county"
   # Should show 'zip' not 'col__zip'
   ```

## Part 2 Fixes (API Endpoint)

### Issue: All POST requests returning 405 (Method Not Allowed)
- The endpoint `/county_data` didn't exist or didn't accept POST

### Fixes Applied:
1. ✅ Created `/county_data` POST endpoint
2. ✅ Handles JSON POST requests
3. ✅ Validates required fields (`zip`, `measure_name`)
4. ✅ Returns 418 for `coffee=teapot`
5. ✅ Returns 400 for missing required fields
6. ✅ Returns 404 for not found
7. ✅ Updated `link.txt` to point to `/county_data`

### Action Required:
1. **Deploy the updated API** to Vercel
2. **Test the endpoint**:
   ```bash
   curl -X POST https://michelleweon-hw4.vercel.app/county_data \
     -H "Content-Type: application/json" \
     -d '{"zip":"02138","measure_name":"Adult obesity"}'
   ```

## Testing Checklist

### Part 1 Tests:
- [ ] Regenerate database with fixed script
- [ ] Verify `zip_county` table has `zip` column (not `col__zip`)
- [ ] Verify `county_health_rankings` schema matches expected
- [ ] Test with hw4test.csv to ensure `field_one` works

### Part 2 Tests:
- [ ] Test POST to `/county_data` with valid data
- [ ] Test POST with `coffee=teapot` (should return 418)
- [ ] Test POST with missing `zip` (should return 400)
- [ ] Test POST with missing `measure_name` (should return 400)
- [ ] Test POST with invalid ZIP (should return 404)
- [ ] Test POST with invalid measure_name (should return 404)
- [ ] Test wrong endpoint (should return 404)

## Expected Test Results

After fixes, you should get:
- Part 1: 15/15 points
- Part 2: 35/35 points
- **Total: 50/50 points**

## Key Points

1. **Column Names**: The CSV headers should be preserved as-is (only spaces replaced with underscores, and `col_` prefix only for numeric-starting names)

2. **API Endpoint**: Must be `/county_data` (not `/api/county_data`) and accept POST requests

3. **Error Codes**: 
   - 418 for teapot
   - 400 for bad request
   - 404 for not found
   - 500 should not occur (autograder checks this)

4. **Response Format**: Must return JSON array of health ranking records matching the database schema (lowercase with underscores)
