# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CIE-H14A Modbus TCP/IP Control System - A Flask-based web application for monitoring and controlling a 4-channel digital I/O controller (CIE-H14A) via Modbus TCP/IP protocol.

**Technology Stack:**
- Backend: Python 3.11+, Flask 3.0
- Modbus: pyModbusTCP 0.2.0
- Frontend: HTML5, CSS3, JavaScript (Vanilla), Bootstrap 5
- Real-time: Server-Sent Events (SSE)
- Containerization: Docker & Docker Compose
- WSGI Server: Gunicorn

## Development Commands

### Local Development

```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Run development server
python run.py

# Alternative: Flask CLI
export FLASK_APP=app
export FLASK_ENV=development
flask run --host=0.0.0.0 --port=5000
```

### Docker

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Rebuild after code changes
docker-compose up --build

# Stop containers
docker-compose down

# Access container shell
docker exec -it modbus-controller bash
```

### Testing

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run all tests
pytest

# Run with coverage report
pytest --cov=app tests/

# Test specific file
pytest tests/test_modbus_client.py
```

## Project Architecture

### Core Components

1. **Modbus Client Layer** (`app/modbus_client.py`)
   - `CIE_H14A_Client` class manages Modbus TCP/IP communication
   - Handles connection lifecycle, reconnection logic, and state management
   - Read operations: Function Code 02 (Read Discrete Inputs) for DI0-DI3 (addresses 0-3)
   - Write operations: Function Code 05 (Write Single Coil) for DO0-DO3 (addresses 8-11)
   - Background polling thread for real-time input monitoring
   - Thread-safe operations with locks for concurrent access

2. **Flask API Layer** (`app/routes.py`)
   - REST API endpoints for status queries and output control
   - SSE endpoint (`/api/events`) for real-time updates to web clients
   - Translates HTTP requests to Modbus operations

3. **Web Interface** (`app/static/`)
   - Single-page application with Bootstrap 5 UI
   - `main.js`: Handles EventSource connection for SSE, manages UI state updates
   - `style.css`: Responsive design for mobile/tablet/desktop
   - `index.html`: Dashboard with 4 input indicators and 4 output control buttons

4. **Configuration** (`config/config.py`)
   - Environment-based configuration using python-dotenv
   - Modbus connection parameters (host, port, unit_id, timeout)
   - Polling interval configuration

### Key Architectural Patterns

- **Threading Model**: Background thread polls Modbus inputs at configured interval (default 500ms), main thread serves HTTP requests
- **State Synchronization**: Shared state protected by threading locks between polling thread and request handlers
- **Error Handling**: Automatic reconnection on connection loss, error propagation to API responses
- **Real-time Updates**: SSE stream pushes state changes to connected clients without polling

### Modbus Register Mapping (CIE-H14A)

| Channel | Type | Function Code | Address | Notes |
|---------|------|---------------|---------|-------|
| DI0-DI3 | Input | FC 02 (Read Discrete Inputs) | 0-3 | Digital inputs |
| DO0-DO3 | Output | FC 05 (Write Single Coil) | 8-11 | Relay outputs |

**Important**: Input addresses are 0-3, output addresses are 8-11 (not 0-3). Do not confuse these ranges.

## API Endpoints

### Core Endpoints

- `GET /api/status` - Returns current connection status and all I/O states
- `POST /api/output/<channel>` - Control specific output (body: `{"state": true/false}`)
- `POST /api/output/<channel>/toggle` - Toggle output state
- `GET /api/events` - SSE stream for real-time updates
- `GET /api/config` - View current Modbus configuration
- `GET /health` - Health check endpoint

## Environment Configuration

Required environment variables in `.env`:

```env
MODBUS_HOST=10.1.0.1        # CIE-H14A IP address
MODBUS_PORT=502             # Modbus TCP port
MODBUS_UNIT_ID=1            # Modbus unit/slave ID
MODBUS_TIMEOUT=5.0          # Connection timeout in seconds
POLL_INTERVAL=0.5           # Input polling interval in seconds
FLASK_ENV=development       # Flask environment (development/production)
SECRET_KEY=your-secret      # Flask secret key
```

## Common Development Patterns

### Adding New Modbus Features

When adding new Modbus functionality:
1. Add methods to `CIE_H14A_Client` class for register access
2. Ensure thread safety using the existing lock mechanism
3. Add corresponding API endpoints in `routes.py`
4. Update frontend `main.js` to handle new data
5. Write tests in `tests/` directory

### Modbus Connection Management

The system implements automatic reconnection:
- Connection failures trigger immediate reconnection attempts
- Polling thread handles connection state
- API returns connection status in all responses
- Frontend displays connection indicator

### Frontend Updates

When modifying the web interface:
- Maintain responsive design (mobile-first)
- Update `main.js` to handle SSE data changes
- Keep Bootstrap 5 component patterns
- Test on multiple screen sizes

## Important Notes

### Critical Behaviors

1. **Single Modbus Connection**: Only one Modbus connection exists per application instance. Multiple workers/processes will cause conflicts.
2. **Gunicorn Configuration**: When using Gunicorn in production, use `--workers 1` to maintain single connection
3. **Threading Constraints**: Background polling thread must be stopped gracefully on shutdown to prevent resource leaks
4. **Address Offset**: Modbus output addresses start at 8, not 0. Always add 8 to output channel numbers.
5. **CIE-H14A Limitations**: Device supports 4 channels only. Channel numbers must be 0-3.

### Error Scenarios

- **Connection Loss**: System attempts automatic reconnection every poll interval
- **Invalid Channel**: API returns 400 error for channels outside 0-3 range
- **Modbus Timeout**: Timeout errors logged and reported via API
- **SSE Disconnect**: Clients should implement reconnection logic with exponential backoff

### Testing Considerations

- **Modbus Simulator**: Use `pymodbus.server` or ModbusPal for testing without hardware
- **Integration Tests**: Require actual CIE-H14A device or simulator on network
- **Unit Tests**: Mock `ModbusClient` for isolated testing

## Future Roadmap

Planned features (not yet implemented):
- User authentication and authorization
- Database integration for I/O history
- Email/Slack notifications on input changes
- Multi-device support
- Data visualization (charts, graphs)
- Pulse control (Modbus FC 105)
- Mobile app

When implementing these, ensure backward compatibility with existing API endpoints.

## Troubleshooting

### Common Issues

**Modbus Connection Failures:**
- Verify CIE-H14A IP address and network connectivity (`ping` test)
- Check firewall allows TCP port 502
- Confirm Modbus TCP is enabled on CIE-H14A (use ezManager tool)
- Verify correct Unit ID configuration

**Docker Network Issues:**
- If container cannot reach host network device, use `network_mode: host` in `docker-compose.yml`
- Check Docker network settings allow bridge mode access

**SSE Connection Drops:**
- Proxy servers may timeout long-lived connections
- Implement client-side reconnection logic
- Check server logs for connection errors

**Port Conflicts:**
- Default port 5000 may conflict with other services
- Change port in `.env` or `docker-compose.yml`

## Code Quality Standards

- Follow PEP 8 for Python code style
- Use type hints where applicable
- Add docstrings to all public methods
- Handle exceptions gracefully with logging
- Validate all user inputs
- Use environment variables for configuration (never hardcode)
