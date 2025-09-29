from flask import Flask, render_template, request, jsonify
import sqlite3
import os

app = Flask(__name__)

# Database configuration
DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data.db')

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/')
def index():
    return render_template('index.html')

# =============================================================================
# COUNTY DATA API ENDPOINTS
# =============================================================================

@app.route('/api/county_data', methods=['GET'])
def get_county_data():
    """Get all counties with basic information"""
    try:
        conn = get_db_connection()
        
        # Get query parameters
        state = request.args.get('state')
        limit = request.args.get('limit', type=int)
        
        # Build query
        query = """
        SELECT DISTINCT 
            z.county,
            z.state_abbreviation as state,
            z.default_city,
            COUNT(z.col__zip) as zip_count
        FROM zip_county z
        """
        
        params = []
        if state:
            query += " WHERE z.state_abbreviation = ?"
            params.append(state)
            
        query += " GROUP BY z.county, z.state_abbreviation, z.default_city ORDER BY z.county"
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        counties = conn.execute(query, params).fetchall()
        conn.close()
        
        result = []
        for county in counties:
            result.append({
                'county': county['county'],
                'state': county['state'],
                'default_city': county['default_city'],
                'zip_count': county['zip_count']
            })
        
        return jsonify({
            'success': True,
            'count': len(result),
            'data': result
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/county_data/<county_name>', methods=['GET'])
def get_county_details(county_name):
    """Get detailed information for a specific county"""
    try:
        conn = get_db_connection()
        state = request.args.get('state')
        
        # Build query for county details
        query = """
        SELECT DISTINCT 
            z.county,
            z.state_abbreviation as state,
            z.default_city,
            COUNT(z.col__zip) as zip_count,
            GROUP_CONCAT(DISTINCT z.col__zip) as zip_codes
        FROM zip_county z
        WHERE z.county = ?
        """
        
        params = [county_name]
        if state:
            query += " AND z.state_abbreviation = ?"
            params.append(state)
            
        query += " GROUP BY z.county, z.state_abbreviation, z.default_city"
        
        county = conn.execute(query, params).fetchone()
        
        if not county:
            conn.close()
            return jsonify({'success': False, 'error': 'County not found'}), 404
        
        # Get health rankings for this county
        health_query = """
        SELECT * FROM county_health_rankings 
        WHERE county = ? AND state = ?
        """
        health_data = conn.execute(health_query, [county['county'], county['state']]).fetchone()
        
        conn.close()
        
        result = {
            'county': county['county'],
            'state': county['state'],
            'default_city': county['default_city'],
            'zip_count': county['zip_count'],
            'zip_codes': county['zip_codes'].split(',') if county['zip_codes'] else [],
            'health_rankings': dict(health_data) if health_data else None
        }
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/zip/<zip_code>', methods=['GET'])
def get_zip_info(zip_code):
    """Get county information by ZIP code"""
    try:
        conn = get_db_connection()
        
        # Get ZIP code info
        zip_query = """
        SELECT * FROM zip_county WHERE col__zip = ?
        """
        zip_data = conn.execute(zip_query, [zip_code]).fetchone()
        
        if not zip_data:
            conn.close()
            return jsonify({'success': False, 'error': 'ZIP code not found'}), 404
        
        # Get health rankings for the county - get key health measures
        health_query = """
        SELECT 
            Measure_name,
            Raw_value,
            Year_span,
            Data_Release_Year
        FROM county_health_rankings 
        WHERE County = ? AND State = ?
        AND Measure_name IN (
            'Violent crime rate',
            'Unemployment', 
            'Children in poverty',
            'Adult obesity',
            'Physical inactivity',
            'Uninsured',
            'Preventable hospital stays'
        )
        ORDER BY Data_Release_Year DESC, Measure_name
        LIMIT 5
        """
        health_data = conn.execute(health_query, [zip_data['county'], zip_data['state']]).fetchall()
        
        conn.close()
        
        result = {
            'zip_code': zip_data['col__zip'],
            'county': zip_data['county'],
            'state': zip_data['state_abbreviation'],
            'default_city': zip_data['default_city'],
            'health_rankings': [dict(health) for health in health_data] if health_data else []
        }
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def calculate_health_score(health_measures):
    """Calculate a health score based on key health metrics (0-100, higher is better)"""
    if not health_measures:
        return 0
    
    score = 100  # Start with perfect score
    weights = {
        'Adult obesity': 0.20,
        'Physical inactivity': 0.15,
        'Children in poverty': 0.15,
        'Unemployment': 0.10,
        'Violent crime rate': 0.15,
        'Uninsured': 0.10,
        'Preventable hospital stays': 0.15
    }
    
    for measure in health_measures:
        measure_name = measure['Measure_name']
        raw_value = measure['Raw_value']
        
        if not raw_value or raw_value == '':
            continue
            
        try:
            value = float(raw_value)
            weight = weights.get(measure_name, 0.1)
            
            # Penalize based on health metrics (lower is better for most)
            if measure_name in ['Adult obesity', 'Physical inactivity', 'Children in poverty', 'Unemployment', 'Uninsured']:
                # These are percentages, penalize more as they increase
                penalty = value * 100  # Convert to percentage
                score -= penalty * weight
            elif measure_name == 'Violent crime rate':
                # Crime rate per 100,000, penalize more as it increases
                penalty = min(value / 10, 10)  # Cap penalty at 10 points
                score -= penalty * weight
            elif measure_name == 'Preventable hospital stays':
                # Hospital stays per 100,000, penalize more as it increases
                penalty = min(value / 100, 5)  # Cap penalty at 5 points
                score -= penalty * weight
                
        except (ValueError, TypeError):
            continue
    
    return max(0, min(100, round(score, 1)))  # Keep between 0-100

@app.route('/api/health_rankings', methods=['GET'])
def get_health_rankings():
    """Get health rankings data with pagination and optimization"""
    try:
        conn = get_db_connection()
        
        # Get query parameters
        county = request.args.get('county')
        state = request.args.get('state')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Limit per_page to prevent excessive load
        per_page = min(per_page, 50)
        
        # Calculate offset
        offset = (page - 1) * per_page
        
        # Build optimized query - get counties with pre-calculated health scores
        query = """
        WITH county_health_scores AS (
            SELECT 
                County,
                State,
                fipscode,
                COUNT(*) as measure_count,
                AVG(CASE 
                    WHEN Measure_name = 'Adult obesity' THEN CAST(Raw_value AS REAL) * 100
                    WHEN Measure_name = 'Physical inactivity' THEN CAST(Raw_value AS REAL) * 100
                    WHEN Measure_name = 'Children in poverty' THEN CAST(Raw_value AS REAL) * 100
                    WHEN Measure_name = 'Unemployment' THEN CAST(Raw_value AS REAL) * 100
                    WHEN Measure_name = 'Uninsured' THEN CAST(Raw_value AS REAL) * 100
                    WHEN Measure_name = 'Violent crime rate' THEN CAST(Raw_value AS REAL) / 10
                    WHEN Measure_name = 'Preventable hospital stays' THEN CAST(Raw_value AS REAL) / 100
                    ELSE 0
                END) as avg_penalty
            FROM county_health_rankings
            WHERE County != 'United States' 
            AND County != State
            AND County LIKE '%County%'
            AND Measure_name IN (
                'Violent crime rate',
                'Unemployment', 
                'Children in poverty',
                'Adult obesity',
                'Physical inactivity',
                'Uninsured',
                'Preventable hospital stays'
            )
            AND Raw_value IS NOT NULL 
            AND Raw_value != ''
            GROUP BY County, State, fipscode
        ),
        ranked_counties AS (
            SELECT 
                County,
                State,
                fipscode,
                measure_count,
                avg_penalty,
                ROW_NUMBER() OVER (PARTITION BY County, State ORDER BY 
                    CASE WHEN fipscode IS NOT NULL AND fipscode != '' THEN 0 ELSE 1 END,
                    measure_count DESC
                ) as rn
            FROM county_health_scores
        )
        SELECT 
            County,
            State,
            fipscode,
            measure_count,
            CASE 
                WHEN avg_penalty IS NULL THEN 0
                ELSE MAX(0, 100 - avg_penalty)
            END as health_score
        FROM ranked_counties
        WHERE rn = 1
        """
        
        params = []
        conditions = []
        
        if county:
            conditions.append("County = ?")
            params.append(county)
        
        if state:
            conditions.append("State = ?")
            params.append(state)
        
        if conditions:
            query += " AND " + " AND ".join(conditions)
        
        query += " ORDER BY health_score DESC"
        query += " LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        
        rankings = conn.execute(query, params).fetchall()
        
        # Convert to result format
        result = []
        for ranking in rankings:
            result.append({
                'county': ranking['County'],
                'state': ranking['State'],
                'fipscode': ranking['fipscode'],
                'measure_count': ranking['measure_count'],
                'health_score': round(ranking['health_score'], 1),
                'health_measures': []  # Will be loaded on demand
            })
        
        # Get total count for pagination
        count_query = """
        SELECT COUNT(DISTINCT County || ', ' || State) as total
        FROM county_health_rankings
        WHERE County != 'United States' 
        AND County != State
        AND County LIKE '%County%'
        """
        count_params = []
        count_conditions = []
        
        if county:
            count_conditions.append("County = ?")
            count_params.append(county)
        
        if state:
            count_conditions.append("State = ?")
            count_params.append(state)
        
        if count_conditions:
            count_query += " AND " + " AND ".join(count_conditions)
        
        total_count = conn.execute(count_query, count_params).fetchone()['total']
        
        conn.close()
        
        return jsonify({
            'success': True,
            'count': len(result),
            'total': total_count,
            'page': page,
            'per_page': per_page,
            'total_pages': (total_count + per_page - 1) // per_page,
            'data': result
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/health_rankings/<county>/<state>', methods=['GET'])
def get_county_health_details(county, state):
    """Get detailed health measures for a specific county"""
    try:
        conn = get_db_connection()
        
        # Use the same health score calculation as the rankings page
        score_query = """
        WITH county_health_scores AS (
            SELECT 
                AVG(CASE 
                    WHEN Measure_name = 'Adult obesity' THEN CAST(Raw_value AS REAL) * 100
                    WHEN Measure_name = 'Physical inactivity' THEN CAST(Raw_value AS REAL) * 100
                    WHEN Measure_name = 'Children in poverty' THEN CAST(Raw_value AS REAL) * 100
                    WHEN Measure_name = 'Unemployment' THEN CAST(Raw_value AS REAL) * 100
                    WHEN Measure_name = 'Uninsured' THEN CAST(Raw_value AS REAL) * 100
                    WHEN Measure_name = 'Violent crime rate' THEN CAST(Raw_value AS REAL) / 10
                    WHEN Measure_name = 'Preventable hospital stays' THEN CAST(Raw_value AS REAL) / 100
                    ELSE 0
                END) as avg_penalty
            FROM county_health_rankings
            WHERE County = ? AND State = ?
            AND Measure_name IN (
                'Violent crime rate',
                'Unemployment', 
                'Children in poverty',
                'Adult obesity',
                'Physical inactivity',
                'Uninsured',
                'Preventable hospital stays'
            )
            AND Raw_value IS NOT NULL 
            AND Raw_value != ''
        )
        SELECT 
            CASE 
                WHEN avg_penalty IS NULL THEN 0
                ELSE MAX(0, 100 - avg_penalty)
            END as health_score
        FROM county_health_scores
        """
        
        health_score_result = conn.execute(score_query, [county, state]).fetchone()
        health_score = round(health_score_result['health_score'], 1) if health_score_result else 0
        
        # Get key health measures for this county
        health_query = """
        SELECT 
            Measure_name,
            Raw_value,
            Year_span,
            Data_Release_Year
        FROM county_health_rankings 
        WHERE County = ? AND State = ?
        AND Measure_name IN (
            'Violent crime rate',
            'Unemployment', 
            'Children in poverty',
            'Adult obesity',
            'Physical inactivity',
            'Uninsured',
            'Preventable hospital stays'
        )
        ORDER BY Data_Release_Year DESC, Measure_name
        """
        health_measures = conn.execute(health_query, [county, state]).fetchall()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {
                'county': county,
                'state': state,
                'health_score': health_score,
                'health_measures': [dict(measure) for measure in health_measures]
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/search', methods=['GET'])
def search_counties():
    """Search counties by name or state"""
    try:
        query_param = request.args.get('q', '').strip()
        if not query_param:
            return jsonify({'success': False, 'error': 'Query parameter "q" is required'}), 400
        
        conn = get_db_connection()
        
        search_query = """
        SELECT DISTINCT 
            z.county,
            z.state_abbreviation as state,
            z.default_city,
            COUNT(z.col__zip) as zip_count
        FROM zip_county z
        WHERE z.county LIKE ? OR z.state_abbreviation LIKE ?
        GROUP BY z.county, z.state_abbreviation, z.default_city
        ORDER BY z.county
        """
        
        search_term = f"%{query_param}%"
        results = conn.execute(search_query, [search_term, search_term]).fetchall()
        conn.close()
        
        counties = []
        for county in results:
            counties.append({
                'county': county['county'],
                'state': county['state'],
                'default_city': county['default_city'],
                'zip_count': county['zip_count']
            })
        
        return jsonify({
            'success': True,
            'query': query_param,
            'count': len(counties),
            'data': counties
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get overall statistics about the data"""
    try:
        conn = get_db_connection()
        
        # Get counts
        zip_count = conn.execute("SELECT COUNT(*) FROM zip_county").fetchone()[0]
        county_count = conn.execute("SELECT COUNT(DISTINCT county || ', ' || state_abbreviation) FROM zip_county").fetchone()[0]
        state_count = conn.execute("SELECT COUNT(DISTINCT state_abbreviation) FROM zip_county").fetchone()[0]
        health_count = conn.execute("SELECT COUNT(*) FROM county_health_rankings").fetchone()[0]
        
        # Get state distribution
        state_dist = conn.execute("""
            SELECT state_abbreviation as state, COUNT(DISTINCT county) as county_count, COUNT(col__zip) as zip_count
            FROM zip_county 
            GROUP BY state_abbreviation 
            ORDER BY county_count DESC
        """).fetchall()
        
        conn.close()
        
        state_distribution = []
        for state in state_dist:
            state_distribution.append({
                'state': state['state'],
                'county_count': state['county_count'],
                'zip_count': state['zip_count']
            })
        
        return jsonify({
            'success': True,
            'data': {
                'total_zip_codes': zip_count,
                'total_counties': county_count,
                'total_states': state_count,
                'total_health_records': health_count,
                'state_distribution': state_distribution
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================================================================
# LOCATION-BASED SERVICES API
# =============================================================================

@app.route('/api/location/zip/<zip_code>', methods=['GET'])
def get_zip_location_details(zip_code):
    """Enhanced ZIP code lookup with comprehensive location data"""
    try:
        conn = get_db_connection()
        
        # Get ZIP code info with all related data
        zip_query = """
        SELECT 
            z.col__zip as zip_code,
            z.county,
            z.state_abbreviation as state,
            z.default_city,
            COUNT(DISTINCT z2.col__zip) as total_zips_in_county,
            COUNT(DISTINCT z3.col__zip) as total_zips_in_city
        FROM zip_county z
        LEFT JOIN zip_county z2 ON z2.county = z.county AND z2.state_abbreviation = z.state_abbreviation
        LEFT JOIN zip_county z3 ON z3.default_city = z.default_city
        WHERE z.col__zip = ?
        GROUP BY z.col__zip, z.county, z.state_abbreviation, z.default_city
        """
        
        zip_data = conn.execute(zip_query, [zip_code]).fetchone()
        
        if not zip_data:
            conn.close()
            return jsonify({'success': False, 'error': 'ZIP code not found'}), 404
        
        # Get health rankings for the county - get key health measures
        health_query = """
        SELECT 
            Measure_name,
            Raw_value,
            Year_span,
            Data_Release_Year
        FROM county_health_rankings 
        WHERE County = ? AND State = ?
        AND Measure_name IN (
            'Violent crime rate',
            'Unemployment', 
            'Children in poverty',
            'Adult obesity',
            'Physical inactivity',
            'Uninsured',
            'Preventable hospital stays'
        )
        ORDER BY Data_Release_Year DESC, Measure_name
        LIMIT 10
        """
        health_data = conn.execute(health_query, [zip_data['county'], zip_data['state']]).fetchall()
        
        # Get all ZIP codes in the same county
        county_zips_query = """
        SELECT col__zip FROM zip_county 
        WHERE county = ? AND state_abbreviation = ?
        ORDER BY col__zip
        """
        county_zips = conn.execute(county_zips_query, [zip_data['county'], zip_data['state']]).fetchall()
        
        # Get all ZIP codes in the same city
        city_zips_query = """
        SELECT col__zip, county, state_abbreviation FROM zip_county 
        WHERE default_city = ?
        ORDER BY county, col__zip
        """
        city_zips = conn.execute(city_zips_query, [zip_data['default_city']]).fetchall()
        
        conn.close()
        
        result = {
            'zip_code': zip_data['zip_code'],
            'location': {
                'county': zip_data['county'],
                'state': zip_data['state'],
                'default_city': zip_data['default_city']
            },
            'statistics': {
                'total_zips_in_county': zip_data['total_zips_in_county'],
                'total_zips_in_city': zip_data['total_zips_in_city']
            },
            'health_rankings': [dict(health) for health in health_data] if health_data else [],
            'county_zips': [zip['col__zip'] for zip in county_zips],
            'city_zips': [
                {
                    'zip_code': zip['col__zip'],
                    'county': zip['county'],
                    'state': zip['state_abbreviation']
                } for zip in city_zips
            ]
        }
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/location/cities', methods=['GET'])
def get_cities():
    """Get all cities with statistics"""
    try:
        conn = get_db_connection()
        
        # Get query parameters
        state = request.args.get('state')
        limit = request.args.get('limit', type=int)
        
        # Build query
        query = """
        SELECT 
            default_city,
            COUNT(DISTINCT county || ', ' || state_abbreviation) as county_count,
            COUNT(DISTINCT state_abbreviation) as state_count,
            COUNT(col__zip) as zip_count,
            GROUP_CONCAT(DISTINCT state_abbreviation) as states
        FROM zip_county
        WHERE default_city IS NOT NULL AND default_city != ''
        """
        
        params = []
        if state:
            query += " AND state_abbreviation = ?"
            params.append(state)
            
        query += " GROUP BY default_city ORDER BY zip_count DESC"
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        cities = conn.execute(query, params).fetchall()
        conn.close()
        
        result = []
        for city in cities:
            result.append({
                'city': city['default_city'],
                'county_count': city['county_count'],
                'state_count': city['state_count'],
                'zip_count': city['zip_count'],
                'states': city['states'].split(',') if city['states'] else []
            })
        
        return jsonify({
            'success': True,
            'count': len(result),
            'data': result
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/location/metro_areas/<metro_name>', methods=['GET'])
def get_metro_area_details(metro_name):
    """Get detailed information about a specific metro area"""
    try:
        conn = get_db_connection()
        
        # Get metro area details
        metro_query = """
        SELECT 
            metro_area,
            COUNT(DISTINCT county || ', ' || state) as county_count,
            COUNT(DISTINCT state) as state_count,
            COUNT(zip_code) as zip_count,
            GROUP_CONCAT(DISTINCT state) as states
        FROM zip_county
        WHERE metro_area = ?
        GROUP BY metro_area
        """
        
        metro_data = conn.execute(metro_query, [metro_name]).fetchone()
        
        if not metro_data:
            conn.close()
            return jsonify({'success': False, 'error': 'Metro area not found'}), 404
        
        # Get all counties in this metro area
        counties_query = """
        SELECT DISTINCT 
            county,
            state,
            COUNT(zip_code) as zip_count
        FROM zip_county
        WHERE metro_area = ?
        GROUP BY county, state
        ORDER BY county
        """
        counties = conn.execute(counties_query, [metro_name]).fetchall()
        
        # Get all ZIP codes in this metro area
        zips_query = """
        SELECT zip_code, county, state
        FROM zip_county
        WHERE metro_area = ?
        ORDER BY county, zip_code
        """
        zips = conn.execute(zips_query, [metro_name]).fetchall()
        
        # Get health rankings for all counties in this metro area
        health_query = """
        SELECT h.*, z.metro_area
        FROM county_health_rankings h
        JOIN zip_county z ON h.county = z.county AND h.state = z.state
        WHERE z.metro_area = ?
        ORDER BY h.health_outcomes_rank
        """
        health_rankings = conn.execute(health_query, [metro_name]).fetchall()
        
        conn.close()
        
        result = {
            'metro_area': metro_data['metro_area'],
            'statistics': {
                'county_count': metro_data['county_count'],
                'state_count': metro_data['state_count'],
                'zip_count': metro_data['zip_count'],
                'states': metro_data['states'].split(',') if metro_data['states'] else []
            },
            'counties': [
                {
                    'county': county['county'],
                    'state': county['state'],
                    'zip_count': county['zip_count']
                } for county in counties
            ],
            'zip_codes': [
                {
                    'zip_code': zip['zip_code'],
                    'county': zip['county'],
                    'state': zip['state']
                } for zip in zips
            ],
            'health_rankings': [dict(health) for health in health_rankings]
        }
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/location/states', methods=['GET'])
def get_states():
    """Get all states with statistics"""
    try:
        conn = get_db_connection()
        
        # Get query parameters
        limit = request.args.get('limit', type=int)
        
        query = """
        SELECT 
            state_abbreviation as state,
            COUNT(DISTINCT county) as county_count,
            COUNT(DISTINCT default_city) as city_count,
            COUNT(col__zip) as zip_count
        FROM zip_county
        GROUP BY state_abbreviation
        ORDER BY county_count DESC
        """
        
        params = []
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        states = conn.execute(query, params).fetchall()
        conn.close()
        
        result = []
        for state in states:
            result.append({
                'state': state['state'],
                'county_count': state['county_count'],
                'city_count': state['city_count'],
                'zip_count': state['zip_count']
            })
        
        return jsonify({
            'success': True,
            'count': len(result),
            'data': result
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/location/states/<state_code>', methods=['GET'])
def get_state_details(state_code):
    """Get detailed information about a specific state"""
    try:
        conn = get_db_connection()
        
        # Get state details
        state_query = """
        SELECT 
            state,
            COUNT(DISTINCT county) as county_count,
            COUNT(DISTINCT metro_area) as metro_count,
            COUNT(zip_code) as zip_count
        FROM zip_county
        WHERE state = ?
        GROUP BY state
        """
        
        state_data = conn.execute(state_query, [state_code]).fetchone()
        
        if not state_data:
            conn.close()
            return jsonify({'success': False, 'error': 'State not found'}), 404
        
        # Get all counties in this state
        counties_query = """
        SELECT DISTINCT 
            county,
            metro_area,
            COUNT(zip_code) as zip_count
        FROM zip_county
        WHERE state = ?
        GROUP BY county, metro_area
        ORDER BY county
        """
        counties = conn.execute(counties_query, [state_code]).fetchall()
        
        # Get all metro areas in this state
        metros_query = """
        SELECT DISTINCT 
            metro_area,
            COUNT(DISTINCT county) as county_count,
            COUNT(zip_code) as zip_count
        FROM zip_county
        WHERE state = ? AND metro_area IS NOT NULL AND metro_area != ''
        GROUP BY metro_area
        ORDER BY zip_count DESC
        """
        metros = conn.execute(metros_query, [state_code]).fetchall()
        
        # Get health rankings for all counties in this state
        health_query = """
        SELECT * FROM county_health_rankings
        WHERE state = ?
        ORDER BY health_outcomes_rank
        """
        health_rankings = conn.execute(health_query, [state_code]).fetchall()
        
        conn.close()
        
        result = {
            'state': state_data['state'],
            'statistics': {
                'county_count': state_data['county_count'],
                'metro_count': state_data['metro_count'],
                'zip_count': state_data['zip_count']
            },
            'counties': [
                {
                    'county': county['county'],
                    'metro_area': county['metro_area'],
                    'zip_count': county['zip_count']
                } for county in counties
            ],
            'metro_areas': [
                {
                    'metro_area': metro['metro_area'],
                    'county_count': metro['county_count'],
                    'zip_count': metro['zip_count']
                } for metro in metros
            ],
            'health_rankings': [dict(health) for health in health_rankings]
        }
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/location/search', methods=['GET'])
def search_locations():
    """Advanced location search with multiple criteria"""
    try:
        query = request.args.get('q', '').strip()
        location_type = request.args.get('type', 'all')  # all, county, state, metro, zip
        state = request.args.get('state')
        limit = request.args.get('limit', type=int)
        
        if not query:
            return jsonify({'success': False, 'error': 'Query parameter "q" is required'}), 400
        
        # Map common state names to abbreviations
        state_name_mapping = {
            'virginia': 'VA', 'california': 'CA', 'texas': 'TX', 'florida': 'FL',
            'new york': 'NY', 'pennsylvania': 'PA', 'illinois': 'IL', 'ohio': 'OH',
            'georgia': 'GA', 'north carolina': 'NC', 'michigan': 'MI', 'new jersey': 'NJ',
            'tennessee': 'TN', 'indiana': 'IN', 'missouri': 'MO', 'maryland': 'MD',
            'wisconsin': 'WI', 'colorado': 'CO', 'minnesota': 'MN', 'south carolina': 'SC',
            'alabama': 'AL', 'louisiana': 'LA', 'kentucky': 'KY', 'oregon': 'OR',
            'oklahoma': 'OK', 'connecticut': 'CT', 'utah': 'UT', 'iowa': 'IA',
            'nevada': 'NV', 'arkansas': 'AR', 'mississippi': 'MS', 'kansas': 'KS',
            'new mexico': 'NM', 'nebraska': 'NE', 'west virginia': 'WV', 'idaho': 'ID',
            'hawaii': 'HI', 'new hampshire': 'NH', 'maine': 'ME', 'montana': 'MT',
            'rhode island': 'RI', 'delaware': 'DE', 'south dakota': 'SD', 'north dakota': 'ND',
            'alaska': 'AK', 'vermont': 'VT', 'wyoming': 'WY'
        }
        
        # Check if query matches a full state name
        if query.lower() in state_name_mapping:
            query = state_name_mapping[query.lower()]
        
        conn = get_db_connection()
        results = []
        
        # Search ZIP codes
        if location_type in ['all', 'zip']:
            zip_query = """
            SELECT 
                'zip' as type,
                col__zip as name,
                county,
                state_abbreviation as state,
                default_city,
                'ZIP Code' as description
            FROM zip_county
            WHERE col__zip LIKE ?
            """
            params = [f"%{query}%"]
            if state:
                zip_query += " AND state_abbreviation = ?"
                params.append(state)
            
            zip_results = conn.execute(zip_query, params).fetchall()
            results.extend([dict(row) for row in zip_results])
        
        # Search counties
        if location_type in ['all', 'county']:
            county_query = """
            SELECT DISTINCT
                'county' as type,
                county as name,
                county,
                state_abbreviation as state,
                default_city,
                COUNT(col__zip) as zip_count,
                'County' as description
            FROM zip_county
            WHERE county LIKE ?
            """
            params = [f"%{query}%"]
            if state:
                county_query += " AND state_abbreviation = ?"
                params.append(state)
            
            county_query += " GROUP BY county, state_abbreviation, default_city"
            county_results = conn.execute(county_query, params).fetchall()
            results.extend([dict(row) for row in county_results])
        
        # Search cities
        if location_type in ['all', 'metro']:
            city_query = """
            SELECT DISTINCT
                'city' as type,
                default_city as name,
                default_city,
                COUNT(DISTINCT county || ', ' || state_abbreviation) as county_count,
                COUNT(col__zip) as zip_count,
                'City' as description
            FROM zip_county
            WHERE default_city LIKE ? AND default_city IS NOT NULL AND default_city != ''
            """
            params = [f"%{query}%"]
            if state:
                city_query += " AND state_abbreviation = ?"
                params.append(state)
            
            city_query += " GROUP BY default_city"
            city_results = conn.execute(city_query, params).fetchall()
            results.extend([dict(row) for row in city_results])
        
        # Search states
        if location_type in ['all', 'state']:
            state_query = """
            SELECT DISTINCT
                'state' as type,
                state_abbreviation as name,
                state_abbreviation as state,
                COUNT(DISTINCT county) as county_count,
                COUNT(col__zip) as zip_count,
                'State' as description
            FROM zip_county
            WHERE state_abbreviation LIKE ?
            GROUP BY state_abbreviation
            """
            params = [f"%{query}%"]
            state_results = conn.execute(state_query, params).fetchall()
            results.extend([dict(row) for row in state_results])
        
        conn.close()
        
        # Sort results by relevance and type priority
        type_priority = {'state': 1, 'zip': 2, 'county': 3, 'city': 4}
        
        def sort_key(item):
            # Prioritize exact matches
            is_exact_match = item['name'].upper() == query.upper()
            # Prioritize states for short queries
            is_state_priority = item['type'] == 'state' and len(query) <= 3
            return (not is_exact_match, not is_state_priority, type_priority.get(item['type'], 5), item['name'])
        
        results.sort(key=sort_key)
        
        if limit:
            results = results[:limit]
        
        return jsonify({
            'success': True,
            'query': query,
            'type': location_type,
            'count': len(results),
            'data': results
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/location/analytics', methods=['GET'])
def get_location_analytics():
    """Get location analytics and insights"""
    try:
        conn = get_db_connection()
        
        # Geographic distribution
        state_dist = conn.execute("""
            SELECT 
                state_abbreviation as state,
                COUNT(DISTINCT county) as county_count,
                COUNT(col__zip) as zip_count,
                COUNT(DISTINCT default_city) as city_count
            FROM zip_county
            GROUP BY state_abbreviation
            ORDER BY county_count DESC
        """).fetchall()
        
        # City analysis
        city_analysis = conn.execute("""
            SELECT 
                default_city as city,
                COUNT(DISTINCT county || ', ' || state_abbreviation) as county_count,
                COUNT(DISTINCT state_abbreviation) as state_count,
                COUNT(col__zip) as zip_count
            FROM zip_county
            WHERE default_city IS NOT NULL AND default_city != ''
            GROUP BY default_city
            ORDER BY zip_count DESC
            LIMIT 10
        """).fetchall()
        
        # Health rankings by state
        health_by_state = conn.execute("""
            SELECT 
                h.State as state,
                COUNT(DISTINCT h.County) as county_count,
                COUNT(*) as health_records
            FROM county_health_rankings h
            WHERE h.County != 'United States' 
            AND h.County != h.State
            AND h.County LIKE '%County%'
            GROUP BY h.State
            ORDER BY county_count DESC
        """).fetchall()
        
        conn.close()
        
        result = {
            'geographic_distribution': [
                {
                    'state': state['state'],
                    'county_count': state['county_count'],
                    'zip_count': state['zip_count'],
                    'city_count': state['city_count']
                } for state in state_dist
            ],
            'top_cities': [
                {
                    'city': city['city'],
                    'county_count': city['county_count'],
                    'state_count': city['state_count'],
                    'zip_count': city['zip_count']
                } for city in city_analysis
            ],
            'health_by_state': [
                {
                    'state': health['state'],
                    'county_count': health['county_count'],
                    'health_records': health['health_records']
                } for health in health_by_state
            ]
        }
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



if __name__ == '__main__':
    app.run(debug=True, port=5001)
