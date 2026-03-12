import { isRouteErrorResponse, Link, useRouteError } from "react-router-dom";

export default function RouteErrorPage() {
  const error = useRouteError();

  let title = "Application error";
  let description =
    "The requested page could not be rendered. Please verify that the required dataset snapshot is available and try again.";
  let statusLabel = "Unexpected error";

  if (isRouteErrorResponse(error)) {
    title = `${error.status} ${error.statusText}`;
    statusLabel = "Route error";

    if (error.status === 404) {
      description =
        "A required route or published data artifact was not found. This usually means the selected dataset snapshot has not been published yet.";
    }
  }

  return (
    <div className="route-error-page">
      <div className="route-error-card">
        <div className="section-label">{statusLabel}</div>
        <h1 className="route-error-card__title">{title}</h1>
        <p className="route-error-card__text">{description}</p>

        <div className="research-annotation-grid">
          <div className="research-annotation">
            <div className="research-annotation__label">Recommended check</div>
            <div className="research-annotation__value">Dataset availability</div>
            <div className="research-annotation__text">
              Confirm that the selected mode points to an existing published snapshot:
              <code> /data/demo/... </code> or <code> /data/research/... </code>.
            </div>
          </div>

          <div className="research-annotation">
            <div className="research-annotation__label">Typical cause</div>
            <div className="research-annotation__value">Missing research snapshot</div>
            <div className="research-annotation__text">
              If research mode is selected, run the publish script and ensure the
              frontend public data folders were generated correctly.
            </div>
          </div>
        </div>

        <div className="route-error-card__actions">
          <Link to="/" className="detail-back-link">
            ← Return to overview
          </Link>
          <Link to="/suite-runs" className="detail-back-link">
            Open experiment registry
          </Link>
        </div>
      </div>
    </div>
  );
}