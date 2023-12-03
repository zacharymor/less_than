import os
from flask import Flask, request, redirect, session, jsonify, render_template
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
import dotenv

dotenv.load_dotenv()
# ------------------------------
# Configuration
# ------------------------------

SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI')
SCOPE = 'playlist-read-private user-library-read playlist-modify-public'

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Generate a random secret key

# ------------------------------
# Spotify OAuth Setup
# ------------------------------

sp_oauth = SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope=SCOPE
)

# ------------------------------
# Spotify Service Class
# ------------------------------

class SpotifyService:
    def __init__(self, auth_token):
        self.sp = Spotify(auth=auth_token)

    def get_my_playlists(self):
        return self.sp.current_user_playlists()

    def get_playlist_tracks(self, playlist_id):
        tracks = []
        results = self.sp.playlist_tracks(playlist_id)
        tracks.extend(results['items'])
        while results['next']:
            results = self.sp.next(results)
            tracks.extend(results['items'])
        return tracks

    def get_liked_songs(self):
        liked_songs = []
        results = self.sp.current_user_saved_tracks()
        liked_songs.extend(results['items'])
        while results['next']:
            results = self.sp.next(results)
            liked_songs.extend(results['items'])
        return liked_songs

    def filter_tracks_by_duration(self, tracks, max_duration_ms):
        return [track for track in tracks if track['track']['duration_ms'] < max_duration_ms]

# ------------------------------
# Route Handlers
# ------------------------------

@app.route('/')
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session['token_info'] = token_info
    return redirect('/profile')

@app.route('/profile')
def profile():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')
    spotify_service = SpotifyService(token_info['access_token'])
    user_profile = spotify_service.sp.current_user()
    return jsonify(user_profile)

@app.route('/playlist-details/<playlist_id>')
def playlist_details(playlist_id):
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')
    spotify_service = SpotifyService(token_info['access_token'])
    tracks = spotify_service.get_playlist_tracks(playlist_id)
    filtered_tracks = spotify_service.filter_tracks_by_duration(tracks, 120000)  # 2 minutes in milliseconds
    return jsonify(filtered_tracks)

@app.route('/liked-songs')
def liked_songs():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')
    spotify_service = SpotifyService(token_info['access_token'])
    liked_songs = spotify_service.sp.current_user_saved_tracks()
    return jsonify(liked_songs)

@app.route('/generate-playlist-from-liked')
def generate_playlist_from_liked():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')

    spotify_service = SpotifyService(token_info['access_token'])

    # Fetch liked songs with pagination support
    liked_tracks = spotify_service.get_liked_songs()

    # Corrected list comprehension
    short_tracks = [track['track']['id'] for track in liked_tracks
                    if track['track']['duration_ms'] < 120000]
    # Handle the case where no tracks meet the criteria
    if not short_tracks:
        return jsonify({'error': 'No tracks found under 2 minutes'})

    # Create a new playlist from the filtered tracks
    user_id = spotify_service.sp.current_user()['id']
    playlist_name = 'Liked Short Tracks Playlist'
    new_playlist = spotify_service.sp.user_playlist_create(user_id, playlist_name, public=True)

    # Add the filtered short tracks to the new playlist
    spotify_service.sp.user_playlist_add_tracks(user_id, new_playlist['id'], short_tracks)

    return jsonify({'new_playlist_name': new_playlist['name']})

@app.route('/generate-playlist')
def generate_playlist():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')

    spotify_service = SpotifyService(token_info['access_token'])

    # Fetch tracks from a source, e.g., the user's saved tracks
    # This can be changed based on where you want to fetch the tracks from
    saved_tracks = spotify_service.sp.current_user_saved_tracks()

    # Filter tracks that are less than 2 minutes (120000 milliseconds)
    short_tracks = [track['track']['id'] for track in saved_tracks['items'] 
                    if track['track']['duration_ms'] < 120000]

    # Handle the case where no tracks meet the criteria
    if not short_tracks:
        return jsonify({'error': 'No tracks found under 2 minutes'})

    # Create a new playlist
    user_id = spotify_service.sp.current_user()['id']
    playlist_name = 'Short Tracks Playlist'
    new_playlist = spotify_service.sp.user_playlist_create(user_id, playlist_name, public=True)

    # Add the filtered short tracks to the new playlist
    spotify_service.sp.user_playlist_add_tracks(user_id, new_playlist['id'], short_tracks)

    return jsonify({'new_playlist_name': new_playlist['name']})

@app.route('/playlist-stats/<playlist_id>')
def playlist_stats(playlist_id):
    token_info = session.get('token_info', None)
    if not token_info:
        return jsonify({'error': 'Not authenticated'})

    spotify_service = SpotifyService(token_info['access_token'])

    tracks = spotify_service.get_playlist_tracks(playlist_id)
    filtered_tracks = spotify_service.filter_tracks_by_duration(tracks, 120000)  # Filtering tracks less than 2 minutes

    # Calculations for all tracks
    total_duration_ms = sum(track['track']['duration_ms'] for track in tracks)
    min_duration_ms = min(track['track']['duration_ms'] for track in tracks)
    max_duration_ms = max(track['track']['duration_ms'] for track in tracks)

    # Calculations for filtered tracks
    filtered_total_duration_ms = sum(track['track']['duration_ms'] for track in filtered_tracks)
    filtered_min_duration_ms = min(track['track']['duration_ms'] for track in filtered_tracks) if filtered_tracks else 0
    filtered_max_duration_ms = max(track['track']['duration_ms'] for track in filtered_tracks) if filtered_tracks else 0

    return jsonify({
        'total_duration_min': total_duration_ms // 60000,
        'min_track_length_sec': min_duration_ms // 1000,
        'max_track_length_sec': max_duration_ms // 1000,
        'filtered_total_duration_min': filtered_total_duration_ms // 60000,
        'filtered_min_track_length_sec': filtered_min_duration_ms // 1000,
        'filtered_max_track_length_sec': filtered_max_duration_ms // 1000
    })

@app.route('/generate')
def generate():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect('/')
    
    spotify_service = SpotifyService(token_info['access_token'])
    playlists = spotify_service.get_my_playlists()

    return render_template('playlists.html', playlists=playlists['items'])


# ------------------------------
# Application Entry Point
# ------------------------------

if __name__ == '__main__':
    app.run(debug=True)
