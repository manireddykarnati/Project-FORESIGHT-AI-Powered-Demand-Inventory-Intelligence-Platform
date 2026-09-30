# Render deployment

The repository includes a Render Blueprint (`render.yaml`) for one **Free Python web service** in Singapore. Python 3.12 is selected by `.python-version`. No database, API key, or persistent disk is required.

## Create the service

In Render, choose **New → Blueprint**, select this GitHub repository and the `main` branch, and review the Free service before deploying. Alternatively, choose **New → Web Service**, connect the repository, and enter these settings:

| Setting | Value |
|---|---|
| Name | `foresight` (or an available unique name) |
| Branch | `main` |
| Runtime | Python 3 |
| Region | Singapore |
| Root directory | Leave blank |
| Instance type | **Free** |
| Build command | `python -m pip install -r requirements-web.txt` |
| Start command | `python -m streamlit run app/streamlit_app.py --server.address=0.0.0.0 --server.port=$PORT --server.headless=true --server.fileWatcherType=none --server.runOnSave=false` |
| Health check path | `/_stcore/health` |

Use the HTTPS URL Render assigns when the deployment is live. Confirm that the dashboard loads, category/product filters work, an unavailable action status produces a clear empty state, and scoring an unknown SKU shows a validation message. A passing HTTP health check only confirms the Streamlit server is up; it does not replace checking the dashboard.

## What runs on the server

The dashboard reads the committed `outputs/` artifacts and recalculates inventory scenarios from those saved inputs. It does **not** retrain models during build or startup. `requirements-web.txt` installs only dashboard dependencies; training and notebook packages remain in `requirements.txt` for local use.

The hosted app retains the source cutoffs, historical stock-review labels, and unconfirmed-currency labels. Hosting does not turn the historical dataset into live inventory or refresh the forecasts. Anyone with the service URL can view the dashboard and its downloads; there is no application login.

## Update the app or data

For code changes, commit and push to the connected branch. If automatic deployment is disabled or the service uses a public Git URL without a provider connection, use **Manual Deploy → Deploy latest commit** in Render.

To refresh analysis, run the full pipeline locally using the supplied source extracts, verify outputs, and commit the regenerated artifacts together. Never add `python run_pipeline.py` to the Render start command. Files written on a Free instance are not durable storage.

Render Free services can sleep after inactivity, so the first visit may take longer. Open the app ahead of a mentor presentation. Current plan limits are maintained in [Render's Free service documentation](https://render.com/docs/free); the deployment configuration explicitly selects the Free instance type.

## Troubleshooting

- **Build fails:** inspect Render's build log and confirm the service uses `requirements-web.txt` and Python 3.12.
- **No open port:** use the exact start command above; bind to `0.0.0.0` and Render's `$PORT`.
- **Cannot load project outputs:** check that the current commit includes the complete `outputs/` directory. Repair and verify artifacts locally, then redeploy.
- **Blank or disconnected page:** wait for a sleeping instance to start, reload, then inspect service logs for application errors or memory limits.

The checked-in configuration is a deployment recipe, not evidence that a service is live. Record and verify the assigned URL after the actual deployment succeeds.
