## Setup

1. **Create Virtual Environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Initialize Database**:
   ```bash
   flask db upgrade
   ```

5. **Seed Database**:
   ```bash
   python seed.py
   ```
   *Default Admin credentials*: `admin@pos.com` / `password123`

6. **Run Application**:
   ```bash
   python app/app.py
   ```

## Testing

Run the test suite with pytest:
```bash
pytest tests/ -v
```
