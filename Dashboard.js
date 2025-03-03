import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container,
  Box,
  Paper,
  Typography,
  Button,
  TextField,
  Grid,
  CircularProgress,
  Alert,
  IconButton,
  AppBar,
  Toolbar,
} from '@mui/material';
import LogoutIcon from '@mui/icons-material/Logout';
import axios from 'axios';

const Dashboard = () => {
  const [streams, setStreams] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [newStream, setNewStream] = useState({
    stream_type: 'udp',
    source: '',
    delay: 0,
    output_type: 'udp',
    output_address: '',
  });
  const navigate = useNavigate();

  const fetchStreams = async () => {
    try {
      const response = await axios.get('http://localhost:8000/streams', {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
      });
      setStreams(Object.entries(response.data));
    } catch (err) {
      if (err.response?.status === 401) {
        localStorage.removeItem('token');
        navigate('/login');
      }
      setError('Failed to fetch streams');
    }
  };

  useEffect(() => {
    fetchStreams();
    const interval = setInterval(fetchStreams, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('token');
    navigate('/login');
  };

  const handleStartStream = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      await axios.post(
        'http://localhost:8000/stream/start',
        newStream,
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem('token')}`,
          },
        }
      );
      fetchStreams();
      setNewStream({
        stream_type: 'udp',
        source: '',
        delay: 0,
        output_type: 'udp',
        output_address: '',
      });
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to start stream');
    } finally {
      setLoading(false);
    }
  };

  const handleStopStream = async (streamId) => {
    try {
      await axios.post(
        `http://localhost:8000/stream/stop/${streamId}`,
        {},
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem('token')}`,
          },
        }
      );
      fetchStreams();
    } catch (err) {
      setError('Failed to stop stream');
    }
  };

  return (
    <>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            Video Delay Server
          </Typography>
          <IconButton color="inherit" onClick={handleLogout}>
            <LogoutIcon />
          </IconButton>
        </Toolbar>
      </AppBar>
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Start New Stream
              </Typography>
              {error && (
                <Alert severity="error" sx={{ mb: 2 }}>
                  {error}
                </Alert>
              )}
              <Box component="form" onSubmit={handleStartStream}>
                <Grid container spacing={2}>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      label="Source"
                      value={newStream.source}
                      onChange={(e) =>
                        setNewStream({ ...newStream, source: e.target.value })
                      }
                      placeholder="udp://239.0.0.1:5000"
                      required
                    />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      label="Output Address"
                      value={newStream.output_address}
                      onChange={(e) =>
                        setNewStream({
                          ...newStream,
                          output_address: e.target.value,
                        })
                      }
                      placeholder="udp://239.0.0.2:5000"
                      required
                    />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      type="number"
                      label="Delay (seconds)"
                      value={newStream.delay}
                      onChange={(e) =>
                        setNewStream({
                          ...newStream,
                          delay: parseFloat(e.target.value),
                        })
                      }
                      required
                    />
                  </Grid>
                  <Grid item xs={12}>
                    <Button
                      type="submit"
                      variant="contained"
                      disabled={loading}
                      sx={{ mt: 2 }}
                    >
                      {loading ? <CircularProgress size={24} /> : 'Start Stream'}
                    </Button>
                  </Grid>
                </Grid>
              </Box>
            </Paper>
          </Grid>
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Active Streams
              </Typography>
              <Grid container spacing={2}>
                {streams.map(([id, stream]) => (
                  <Grid item xs={12} key={id}>
                    <Paper sx={{ p: 2 }} variant="outlined">
                      <Grid container alignItems="center" spacing={2}>
                        <Grid item xs>
                          <Typography variant="subtitle1">
                            Source: {stream.source}
                          </Typography>
                          <Typography variant="body2" color="text.secondary">
                            Output: {stream.output_address}
                          </Typography>
                          <Typography variant="body2" color="text.secondary">
                            Delay: {stream.delay} seconds
                          </Typography>
                        </Grid>
                        <Grid item>
                          <Button
                            variant="outlined"
                            color="error"
                            onClick={() => handleStopStream(id)}
                          >
                            Stop
                          </Button>
                        </Grid>
                      </Grid>
                    </Paper>
                  </Grid>
                ))}
                {streams.length === 0 && (
                  <Grid item xs={12}>
                    <Typography color="text.secondary" align="center">
                      No active streams
                    </Typography>
                  </Grid>
                )}
              </Grid>
            </Paper>
          </Grid>
        </Grid>
      </Container>
    </>
  );
};

export default Dashboard;
