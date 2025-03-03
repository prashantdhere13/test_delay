import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Login from './components/Login';
import ProtectedRoute from './components/ProtectedRoute';
import { 
  Container, 
  Box, 
  Button, 
  Slider, 
  Typography, 
  Paper,
  CircularProgress
} from '@mui/material';
import axios from 'axios';

const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
  },
});

function App() {
  const [videoId, setVideoId] = React.useState(null);
  const [delay, setDelay] = React.useState(0);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState(null);

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    setLoading(true);
    setError(null);

    try {
      const response = await axios.post('http://localhost:8000/upload', formData);
      setVideoId(response.data.video_id);
    } catch (err) {
      setError('Error uploading video. Please try again.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelayChange = (event, newValue) => {
    setDelay(newValue);
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Container maxWidth="md">
                  <Box sx={{ my: 4 }}>
                    <Typography variant="h4" component="h1" gutterBottom align="center">
                      Video Delay Server
                    </Typography>

                    <Paper sx={{ p: 3, mb: 3 }}>
                      <Box sx={{ mb: 3 }}>
                        <input
                          accept="video/*"
                          style={{ display: 'none' }}
                          id="video-upload"
                          type="file"
                          onChange={handleFileUpload}
                        />
                        <label htmlFor="video-upload">
                          <Button
                            variant="contained"
                            component="span"
                            fullWidth
                            disabled={loading}
                          >
                            {loading ? <CircularProgress size={24} /> : 'Upload Video'}
                          </Button>
                        </label>
                      </Box>

                      {error && (
                        <Typography color="error" sx={{ mb: 2 }}>
                          {error}
                        </Typography>
                      )}

                      {videoId && (
                        <>
                          <Typography gutterBottom>
                            Delay: {delay} seconds
                          </Typography>
                          <Slider
                            value={delay}
                            onChange={handleDelayChange}
                            min={0}
                            max={10}
                            step={0.5}
                            marks
                            valueLabelDisplay="auto"
                            sx={{ mb: 3 }}
                          />
                          <Box
                            component="img"
                            sx={{
                              width: '100%',
                              height: 'auto',
                              border: '1px solid #ccc',
                              borderRadius: 1
                            }}
                            src={`http://localhost:8000/stream/${videoId}?delay=${delay}`}
                            alt="Delayed video stream"
                          />
                        </>
                      )}
                    </Paper>
                  </Box>
                </Container>
              </ProtectedRoute>
            }
          />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Router>
    </ThemeProvider>
  );
}

export default App;
