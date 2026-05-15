# Session Changes

## Goal

Align the new prequestionnaire frontend form (9 fields) with the backend `POST /api/auth/` endpoint so form data is persisted to MongoDB and a session cookie is issued.

---

## Files Changed

### 1. `provibackend/ProViBackend/app/datamodels/data_schemas.py`

**What:** Replaced old `PreliminaryAnswersRequest` (6 fields: gender/age int/professional_background/experience_time_pm/frequency_pm/expertise_level_pm) with new schema matching the frontend form.

**New model:**
```python
class PreliminaryAnswersRequest(BaseModel):
    gender: str
    age_range: str                   # e.g. "18–24"
    education: str
    role: str
    field_of_study: str
    rating_process_mining: int       # 1–5
    rating_conformance_checking: int # 1–5
    rating_data_visualization: int   # 1–5
    years_experience: int            # 0–15
```

`User` model and `PreEliminaryAnswers` alias left unchanged.

---

### 2. `provibackend/ProViBackend/app/routers/auth.py`

**What:** Three changes.

**a) Added `utils` import** (was missing, needed for `get_current_datetime`):
```python
import ProViBackend.utils.utils as utils
```

**b) Rewrote `POST /auth/`** — old version used wrong request model (`PreEliminaryAnswers` which requires `_id`) and constructed `User` with non-existent fields. New version:
```python
@router.post("/", tags=["auth"])
@router.post("", tags=["auth"], include_in_schema=False)
async def auth(body: ds.PreliminaryAnswersRequest):
    preliminary_id = str(uuid.uuid4())
    preliminary_doc = {"_id": preliminary_id, **body.model_dump()}
    dbc.create_document("PreliminaryAnswers", preliminary_doc)

    user_id = str(uuid.uuid1())
    user_doc = {
        "user_id": user_id,
        "preliminary_id": preliminary_id,
        "knowledge_id": "",
        "insert_datetime": utils.get_current_datetime(),
    }
    dbc.create_document("User", user_doc)

    response = JSONResponse(content={"message": "User created."})
    response.set_cookie(key="provi_user_id", value=user_id,
                        expires=get_expiry(), secure=True, samesite="none")
    return response
```

**c) Dual route decorator** (`"/"` and `""`) — fixes a proxy redirect loop. Next.js strips trailing slashes before forwarding to backend (`/api/auth/` → `http://provibackend/api/auth`). Without the `""` route, FastAPI issued a 307 redirect back to `http://provibackend/api/auth/` (internal hostname), which the browser could not reach, causing a network error. Registering the same handler at both paths eliminates the redirect.

---

### 3. `ProViFrontend/provi-frontend/src/app/prequestionnaire/page.js`

**What:** Added fetch call in `handleContinue` so the form submits to the backend on Continue.

**Changes:**
- Added `submitting` state
- `handleContinue` made `async`
- On valid submit: POSTs 9-field payload to `/api/auth/`, disables button during fetch, shows error banner on failure, redirects to `/knowledgequestion` on success

```js
const [submitting, setSubmitting] = useState(false);

const handleContinue = async () => {
  if (!isValid) { setError("Please complete all fields before continuing."); return; }
  setError(null);
  setSubmitting(true);
  try {
    const payload = {
      gender,
      age_range: ageRange,
      education,
      role,
      field_of_study: fieldOfStudy,
      rating_process_mining:       ratings.processMining,
      rating_conformance_checking: ratings.conformanceChecking,
      rating_data_visualization:   ratings.dataVisualization,
      years_experience: yearsExp,
    };
    const res = await fetch("/api/auth/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(payload),
    });
    if (!res.ok) { setError("Submission failed. Please try again."); return; }
    router.push("/knowledgequestion");
  } catch {
    setError("Network error. Please check your connection and try again.");
  } finally {
    setSubmitting(false);
  }
};
```

Button text changes to `"Submitting…"` during fetch and is disabled.

---

### 4. `ProViFrontend/provi-frontend/src/components/General/ConditionalFooter.js`

**What:** Added `/prequestionnaire` to `HIDDEN_FOOTER_PATHS` to suppress the site-wide footer on the prequestionnaire page (which renders its own sticky footer).

```js
const HIDDEN_FOOTER_PATHS = ["/admin", "/prequestionnaire"];
```

---

### 5. `ProViFrontend/provi-frontend/next.config.mjs`

**What:** Added `skipTrailingSlashRedirect: true` to prevent Next.js from issuing a 308 redirect when the browser requests `/api/auth/` (with trailing slash). Without this, Next.js redirected to `/api/auth` → Next.js proxied to backend without trailing slash → FastAPI's redirect_slashes issued 307 to internal hostname → browser network error.

```js
const nextConfig = {
  devIndicators: false,
  skipTrailingSlashRedirect: true,
  // ...
};
```

---

## MongoDB Result (per form submission)

**Collection `PreliminaryAnswers`**
```json
{
  "_id": "<uuid4>",
  "gender": "Male",
  "age_range": "25–34",
  "education": "Master",
  "role": "Student",
  "field_of_study": "CS",
  "rating_process_mining": 3,
  "rating_conformance_checking": 3,
  "rating_data_visualization": 3,
  "years_experience": 2
}
```

**Collection `User`**
```json
{
  "user_id": "<uuid1>",
  "preliminary_id": "<uuid4 above>",
  "knowledge_id": "",
  "insert_datetime": "2026-05-12T..."
}
```

Cookie `provi_user_id=<user_id>` set on response (`Secure`, `SameSite=none`).

---

## Bugs Fixed

| Bug | Cause | Fix |
|---|---|---|
| `POST /api/auth/` always 422 | Request model required `_id` (used `PreEliminaryAnswers` not `PreliminaryAnswersRequest`) | New `PreliminaryAnswersRequest` model with no `_id` |
| User document not created | `User` constructor used non-existent fields | Rewrote with correct field names |
| Network error on form submit | Double redirect loop: Next.js 308 → backend 307 to internal hostname | `skipTrailingSlashRedirect: true` + dual route decorator on `POST /auth` |
| Two footers on prequestionnaire page | Site-wide `ConditionalFooter` rendered alongside page's own footer | Added `/prequestionnaire` to `HIDDEN_FOOTER_PATHS` |
