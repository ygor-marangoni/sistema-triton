import hashlib
import hmac
import re
from pathlib import Path
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Annotated
from zoneinfo import ZoneInfo
import jwt
from cryptography.fernet import Fernet
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pwdlib import PasswordHash
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.core.config import get_settings
from app.db.session import get_db
from app.models import Alert, CollectionRun, DemandRevision, EnergyTariff, Hydrometer, HydrometerReading, LevelImageReview, LevelImageReviewRevision, LevelReading, LevelStation, MeteorologicalObservation, MeteorologicalStation, MonthlyDemand, Outorga, Property, Reservoir, User
from app.schemas import AdminPropertyIn, AdminUserIn, AdminUserPatch, AlertEvaluationOut, AlertOut, AlertResolveIn, CollectionRunOut, DemandOut, DemandPatch, HydrometerIn, HydrometerOut, HydrometerReadingIn, HydrometerReadingOut, LevelImageConfirmationOut, LevelImageReviewOut, LevelImageReviewRevisionOut, LevelImageSuggestionIn, LevelReadingIn, LevelReadingOut, LevelStationIn, LevelStationOut, LevelStationUpdate, LoginIn, MeteorologicalObservationOut, MeteorologicalStationIn, MeteorologicalStationOut, MeteorologyOut, MeteorologySyncIn, MeteorologySyncOut, OutorgaIn, OutorgaOut, PropertyIn, PropertyOut, PropertyPatch, RegisterIn, ReservoirIn, ReservoirMapOut, ReservoirOut, RulerCalibrationIn, TariffIn, TariffOut, UserOut
from app.services.domain import compare_month, energy_estimate, reservoir_volume, water_balance
from app.services.demo import demo_balance, demo_permit_comparison, demo_weather, is_demo_property
from app.services.alerts import daily_extrapolation_candidates, expired_outorga_candidate, level_quality_review_candidate, missing_outorga_candidate, quality_review_candidate, stale_measurement_candidate
from app.services.geometry import validate_polygon_kml as validate_kml_polygon
from app.integrations.inmet import InmetAdapter, InmetError, load_csv_schema
from app.services.ruler_images import RulerImageError, calibrated_level, persist_original, resolve_private_image, sanitize_original_filename, validate_and_analyze_image

settings = get_settings()
password_hash = PasswordHash.recommended()
app = FastAPI(title="Sistema Triton API", version="0.1.0", description="Monitoramento de água para propriedades irrigadas. OpenAPI disponível em /docs.")
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"], allow_headers=["Content-Type"])


def private_media_root() -> Path:
    directory = Path(settings.media_storage_directory)
    if not directory.is_absolute():
        directory = Path(__file__).resolve().parents[1] / directory
    return directory.resolve()


def _fernet():
    import base64
    key = hashlib.sha256(settings.secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def _cpf_fingerprint(cpf: str) -> str:
    return hmac.new(settings.secret_key.encode(), cpf.encode(), hashlib.sha256).hexdigest()


def _masked_cpf(user: User) -> str:
    try:
        cpf = _fernet().decrypt(user.cpf_encrypted.encode()).decode()
        return f"***.***.***-{cpf[-2:]}"
    except Exception:
        return "***.***.***-**"


def _user_out(user: User) -> dict:
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role, "is_active": user.is_active, "cpf_masked": _masked_cpf(user)}


def _make_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user.id), "iat": now, "exp": now + timedelta(hours=12)}, settings.secret_key, algorithm="HS256")


from fastapi import Request


def cookie_current_user(request: Request, db: Annotated[Session, Depends(get_db)]) -> User:
    raw = request.cookies.get(settings.cookie_name)
    if not raw:
        raise HTTPException(status_code=401, detail="Entre para continuar")
    try:
        payload = jwt.decode(raw, settings.secret_key, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada")
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Conta indisponível")
    return user


CurrentUser = Annotated[User, Depends(cookie_current_user)]
Db = Annotated[Session, Depends(get_db)]


def ensure_property(db: Session, property_id: int, user: User) -> Property:
    prop = db.get(Property, property_id)
    if not prop or (user.role != "admin" and prop.owner_id != user.id):
        raise HTTPException(status_code=404, detail="Propriedade não encontrada")
    return prop


def ensure_reservoir(db: Session, reservoir_id: int, user: User) -> Reservoir:
    reservoir = db.get(Reservoir, reservoir_id)
    if not reservoir:
        raise HTTPException(status_code=404, detail="Reservatório não encontrado")
    ensure_property(db, reservoir.property_id, user)
    return reservoir


def ensure_level_station(db: Session, station_id: int, user: User) -> LevelStation:
    station = db.get(LevelStation, station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    ensure_reservoir(db, station.reservoir_id, user)
    return station


def ensure_level_image_review(db: Session, review_id: int, user: User) -> LevelImageReview:
    review = db.get(LevelImageReview, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Image review not found")
    ensure_property(db, review.property_id, user)
    return review


def append_level_image_revision(db: Session, review: LevelImageReview, user: User, action_name: str, previous: dict, corrected: dict) -> None:
    db.add(LevelImageReviewRevision(
        review_id=review.id,
        user_id=user.id,
        action=action_name,
        previous_values=previous,
        corrected_values=corrected,
    ))


def mark_image_review_pending(review: LevelImageReview, db: Session) -> None:
    if review.status == "confirmed":
        reading = db.scalar(select(LevelReading).where(LevelReading.image_review_id == review.id))
        if reading:
            reading.quality = "inconclusiva: revisao reaberta; confirme a correcao"
    review.status = "pending_review"
    review.confirmed_level_m = None
    review.reviewed_by_id = None
    review.reviewed_at = None


def ensure_outorga(db: Session, outorga_id: int, user: User) -> Outorga:
    outorga = db.get(Outorga, outorga_id)
    if not outorga:
        raise HTTPException(status_code=404, detail="Outorga não encontrada")
    ensure_property(db, outorga.property_id, user)
    return outorga


def property_view(prop: Property) -> dict:
    return {"id": prop.id, "owner_id": prop.owner_id, "name": prop.name, "cep": prop.cep, "city": prop.city, "state": prop.state, "latitude": prop.latitude, "longitude": prop.longitude, "has_boundary": bool(prop.boundary_kml), "created_at": prop.created_at}


def validate_polygon_kml(kml: str):
    try:
        validate_kml_polygon(kml)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/health")
def health(db: Db):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Banco de dados indisponível")
    return {"status": "ok", "service": "triton-api", "database": "connected"}


def _weather_mapping_status() -> tuple[bool, str, list[str]]:
    try:
        schema = load_csv_schema(settings.inmet_csv_schema_json)
        return True, "Mapeamento do arquivo oficial configurado.", sorted(schema.variables)
    except InmetError as exc:
        return False, str(exc), []


@app.put("/properties/{property_id}/meteorology/station", response_model=MeteorologicalStationOut)
def configure_meteorological_station(property_id: int, data: MeteorologicalStationIn, db: Db, user: CurrentUser):
    ensure_property(db, property_id, user)
    records = list(db.scalars(select(MeteorologicalStation).where(MeteorologicalStation.property_id == property_id, MeteorologicalStation.source == "INMET")))
    station = next((item for item in records if item.station_code == data.station_code), None)
    if station is None:
        station = MeteorologicalStation(property_id=property_id, source="INMET", station_code=data.station_code)
        db.add(station)
    for item in records:
        item.is_active = item.id == station.id if station.id is not None else False
    station.name = data.name.strip()
    station.city = data.city.strip() if data.city else None
    station.state = data.state.upper() if data.state else None
    station.latitude = data.latitude
    station.longitude = data.longitude
    station.is_active = True
    db.commit()
    db.refresh(station)
    return station


@app.get("/properties/{property_id}/meteorology", response_model=MeteorologyOut)
def get_meteorology(property_id: int, db: Db, user: CurrentUser, skip: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=500)):
    prop = ensure_property(db, property_id, user)
    if is_demo_property(settings, user, prop):
        result = demo_weather(property_id)
        result["recent_observations"] = result["recent_observations"][skip:skip + limit]
        return result
    station = db.scalar(select(MeteorologicalStation).where(MeteorologicalStation.property_id == property_id, MeteorologicalStation.source == "INMET", MeteorologicalStation.is_active.is_(True)).order_by(MeteorologicalStation.id.desc()))
    configured, configuration_message, configured_variables = _weather_mapping_status()
    if station is None:
        return {"station": None, "configured": configured, "configuration_message": configuration_message, "configured_variables": configured_variables, "latest_observations": [], "recent_observations": [], "last_observation_at": None, "last_collected_at": None, "last_collection": None}
    query = select(MeteorologicalObservation).where(MeteorologicalObservation.property_id == property_id, MeteorologicalObservation.station_id == station.id, MeteorologicalObservation.is_valid.is_(True))
    recent = list(db.scalars(query.order_by(MeteorologicalObservation.observed_at.desc(), MeteorologicalObservation.id.desc()).offset(skip).limit(limit)))
    latest_by_variable: dict[str, MeteorologicalObservation] = {}
    for variable in ("temperature_air", "relative_humidity", "wind_speed", "wind_direction", "precipitation", "solar_radiation"):
        item = db.scalar(query.where(MeteorologicalObservation.variable == variable).order_by(MeteorologicalObservation.observed_at.desc(), MeteorologicalObservation.id.desc()).limit(1))
        if item:
            latest_by_variable[variable] = item
    latest = list(latest_by_variable.values())
    last_collection = db.scalar(select(CollectionRun).where(CollectionRun.property_id == property_id, CollectionRun.station_id == station.id, CollectionRun.source == "INMET").order_by(CollectionRun.started_at.desc()).limit(1))
    return {
        "station": station,
        "configured": configured,
        "configuration_message": configuration_message,
        "configured_variables": configured_variables,
        "latest_observations": latest,
        "recent_observations": recent,
        "last_observation_at": max((item.observed_at for item in latest), default=None),
        "last_collected_at": max((item.collected_at for item in latest), default=None),
        "last_collection": last_collection,
    }


@app.post("/properties/{property_id}/meteorology/sync", response_model=MeteorologySyncOut)
def synchronize_meteorology(property_id: int, data: MeteorologySyncIn, db: Db, user: CurrentUser):
    ensure_property(db, property_id, user)
    station = db.scalar(select(MeteorologicalStation).where(MeteorologicalStation.property_id == property_id, MeteorologicalStation.source == "INMET", MeteorologicalStation.is_active.is_(True)).order_by(MeteorologicalStation.id.desc()))
    if station is None:
        raise HTTPException(status_code=409, detail="Cadastre a estação INMET da propriedade antes de sincronizar")
    current_year = datetime.now(timezone.utc).year
    if data.year > current_year:
        raise HTTPException(status_code=422, detail="O ano solicitado ainda não ocorreu")
    started_at = datetime.now(timezone.utc)
    run = CollectionRun(property_id=property_id, station_id=station.id, source="INMET", requested_year=data.year, started_at=started_at, status="running", imported_count=0)
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        schema = load_csv_schema(settings.inmet_csv_schema_json)
        adapter = InmetAdapter(schema, timeout_seconds=settings.inmet_timeout_seconds, cache_ttl_seconds=settings.inmet_cache_ttl_seconds, max_archive_bytes=settings.inmet_max_archive_bytes, max_uncompressed_bytes=settings.inmet_max_uncompressed_bytes)
        observations = adapter.collect(data.year, station.station_code)
        values = [{
            "property_id": property_id,
            "station_id": station.id,
            "source": "INMET",
            "station_code": station.station_code,
            "variable": item.variable,
            "value": item.value,
            "unit": item.unit,
            "observed_at": item.observed_at,
            "collected_at": item.collected_at,
            "is_valid": True,
            "quality": item.quality,
        } for item in observations]
        inserted_count = 0
        if values:
            dialect = db.get_bind().dialect.name
            if dialect == "postgresql":
                statement = pg_insert(MeteorologicalObservation).values(values).on_conflict_do_nothing(constraint="uq_weather_property_station_observation")
            elif dialect == "sqlite":
                statement = sqlite_insert(MeteorologicalObservation).values(values).on_conflict_do_nothing(index_elements=["property_id", "station_id", "variable", "observed_at"])
            else:
                raise InmetError("Banco sem suporte à gravação idempotente habilitado para esta integração.")
            result = db.execute(statement)
            inserted_count = max(result.rowcount or 0, 0)
        last_valid_at = max((item.observed_at for item in observations), default=None)
        run.status = "success"
        run.message = "Arquivo validado; sem valores meteorológicos válidos para esta estação/ano." if not observations else "Arquivo oficial processado; observações brutas preservadas sem validação meteorológica."
        run.imported_count = inserted_count
        run.last_valid_at = last_valid_at
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": run.status, "imported_count": inserted_count, "message": run.message, "last_valid_at": last_valid_at}
    except InmetError as exc:
        db.rollback()
        run = db.get(CollectionRun, run.id)
        run.status = "failed"
        run.message = str(exc)
        run.imported_count = 0
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": run.status, "imported_count": 0, "message": run.message, "last_valid_at": run.last_valid_at}


@app.post("/auth/register", status_code=201, response_model=UserOut)
def register(data: RegisterIn, response: Response, db: Db):
    if data.email.lower() == "demo@example.com":
        raise HTTPException(status_code=409, detail="E-mail reservado para demonstração local")
    user = User(name=data.name.strip(), email=data.email.lower(), password_hash=password_hash.hash(data.password),
                cpf_encrypted=_fernet().encrypt(data.cpf.encode()).decode(), cpf_fingerprint=_cpf_fingerprint(data.cpf),
                business_address=data.business_address.strip(), role="user")
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="E-mail ou CPF já cadastrado")
    db.refresh(user)
    response.set_cookie(settings.cookie_name, _make_token(user), httponly=True, secure=settings.cookie_secure, samesite="lax", max_age=43200, path="/")
    return _user_out(user)


@app.post("/auth/login", response_model=UserOut)
def login(data: LoginIn, response: Response, db: Db):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not user.is_active or not password_hash.verify(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")
    response.set_cookie(settings.cookie_name, _make_token(user), httponly=True, secure=settings.cookie_secure, samesite="lax", max_age=43200, path="/")
    return _user_out(user)


@app.post("/auth/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(settings.cookie_name, path="/", httponly=True, secure=settings.cookie_secure, samesite="lax")
    response.status_code = 204
    return response


@app.get("/auth/me", response_model=UserOut)
def me(user: CurrentUser):
    return _user_out(user)


@app.get("/auth/session")
def session_status(request: Request, db: Db):
    try:
        user = cookie_current_user(request, db)
    except HTTPException as exc:
        if exc.status_code == 401:
            return {"authenticated": False, "user": None}
        raise
    return {"authenticated": True, "user": _user_out(user)}


@app.get("/properties", response_model=list[PropertyOut])
def list_properties(db: Db, user: CurrentUser, skip: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=100)):
    stmt = select(Property).options(selectinload(Property.reservoirs)).order_by(Property.created_at.desc()).offset(skip).limit(limit)
    if user.role != "admin":
        stmt = stmt.where(Property.owner_id == user.id)
    return [property_view(p) for p in db.scalars(stmt).all()]


@app.post("/properties", status_code=201, response_model=PropertyOut)
def create_property(data: PropertyIn, db: Db, user: CurrentUser):
    if data.boundary_kml:
        validate_polygon_kml(data.boundary_kml)
    values = data.model_dump()
    values["state"] = values["state"].upper()
    prop = Property(**values, owner_id=user.id)
    db.add(prop); db.commit(); db.refresh(prop)
    return property_view(prop)


@app.get("/properties/{property_id}", response_model=PropertyOut)
def get_property(property_id: int, db: Db, user: CurrentUser):
    prop = ensure_property(db, property_id, user)
    return property_view(prop)


@app.patch("/properties/{property_id}", response_model=PropertyOut)
def edit_property(property_id: int, data: PropertyPatch, db: Db, user: CurrentUser):
    prop = ensure_property(db, property_id, user)
    values = data.model_dump(exclude_unset=True)
    if values.get("boundary_kml"):
        validate_polygon_kml(values["boundary_kml"])
    if "latitude" in values or "longitude" in values:
        prop.latitude = values.get("latitude")
        prop.longitude = values.get("longitude")
    for key, value in values.items():
        if key not in {"latitude", "longitude"} and value is not None:
            setattr(prop, key, value.upper() if key == "state" else value)
    db.commit(); db.refresh(prop)
    return property_view(prop)


@app.delete("/properties/{property_id}", status_code=204)
def delete_property(property_id: int, db: Db, user: CurrentUser):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Somente administrador pode excluir propriedades")
    prop = ensure_property(db, property_id, user)
    db.delete(prop); db.commit()
    return Response(status_code=204)


@app.get("/admin/users")
def admin_list_users(db: Db, user: CurrentUser, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    if user.role != "admin": raise HTTPException(status_code=403, detail="Acesso restrito ao administrador")
    return [_user_out(u) for u in db.scalars(select(User).order_by(User.id).offset(skip).limit(limit)).all()]


@app.post("/admin/users", status_code=201)
def admin_create_user(data: AdminUserIn, db: Db, user: CurrentUser):
    if user.role != "admin": raise HTTPException(status_code=403, detail="Acesso restrito ao administrador")
    if data.email.lower() == "demo@example.com":
        raise HTTPException(status_code=409, detail="E-mail reservado para demonstração local")
    new_user = User(name=data.name.strip(), email=data.email.lower(), password_hash=password_hash.hash(data.password),
                    cpf_encrypted=_fernet().encrypt(data.cpf.encode()).decode(), cpf_fingerprint=_cpf_fingerprint(data.cpf),
                    business_address=data.business_address.strip(), role=data.role, is_active=data.is_active)
    db.add(new_user)
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail="E-mail ou CPF já cadastrado")
    db.refresh(new_user); return _user_out(new_user)


@app.patch("/admin/users/{user_id}")
def admin_patch_user(user_id: int, data: AdminUserPatch, db: Db, user: CurrentUser):
    if user.role != "admin": raise HTTPException(status_code=403, detail="Acesso restrito ao administrador")
    target = db.get(User, user_id)
    if not target: raise HTTPException(status_code=404, detail="Usuário não encontrado")
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is not None: setattr(target, key, value)
    db.commit(); db.refresh(target); return _user_out(target)


@app.post("/admin/properties", status_code=201, response_model=PropertyOut)
def admin_create_property(data: AdminPropertyIn, db: Db, user: CurrentUser):
    if user.role != "admin": raise HTTPException(status_code=403, detail="Acesso restrito ao administrador")
    owner = db.get(User, data.owner_id)
    if not owner: raise HTTPException(status_code=404, detail="Usuário responsável não encontrado")
    values = data.model_dump(exclude={"owner_id"})
    if values.get("boundary_kml"): validate_polygon_kml(values["boundary_kml"])
    values["state"] = values["state"].upper()
    prop = Property(**values, owner_id=owner.id); db.add(prop); db.commit(); db.refresh(prop); return property_view(prop)


@app.get("/properties/{property_id}/reservoirs", response_model=list[ReservoirOut])
def list_reservoirs(property_id: int, db: Db, user: CurrentUser):
    ensure_property(db, property_id, user)
    return db.scalars(select(Reservoir).where(Reservoir.property_id == property_id).order_by(Reservoir.id)).all()


@app.post("/properties/{property_id}/reservoirs", status_code=201, response_model=ReservoirOut)
def create_reservoir(property_id: int, data: ReservoirIn, db: Db, user: CurrentUser):
    ensure_property(db, property_id, user); validate_polygon_kml(data.geometry_kml)
    reservoir = Reservoir(property_id=property_id, **data.model_dump())
    db.add(reservoir); db.commit(); db.refresh(reservoir)
    return reservoir


@app.get("/reservoirs/{reservoir_id}", response_model=ReservoirOut)
def get_reservoir(reservoir_id: int, db: Db, user: CurrentUser):
    return ensure_reservoir(db, reservoir_id, user)


@app.get("/reservoirs/{reservoir_id}/map-geometry", response_model=ReservoirMapOut)
def get_reservoir_map_geometry(reservoir_id: int, db: Db, user: CurrentUser):
    reservoir = ensure_reservoir(db, reservoir_id, user)
    return {"id": reservoir.id, "property_id": reservoir.property_id, "name": reservoir.name, "geometry_kml": reservoir.geometry_kml}


@app.get("/properties/{property_id}/outorgas", response_model=list[OutorgaOut])
def list_outorgas(property_id: int, db: Db, user: CurrentUser):
    ensure_property(db, property_id, user)
    return db.scalars(select(Outorga).options(selectinload(Outorga.demands)).where(Outorga.property_id == property_id).order_by(Outorga.valid_until.desc())).all()


@app.get("/outorgas", response_model=list[OutorgaOut])
def list_all_outorgas(db: Db, user: CurrentUser, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    stmt = select(Outorga).options(selectinload(Outorga.demands)).join(Property).order_by(Outorga.id.desc()).offset(skip).limit(limit)
    if user.role != "admin": stmt = stmt.where(Property.owner_id == user.id)
    return db.scalars(stmt).all()


@app.post("/outorgas", status_code=201, response_model=OutorgaOut)
def create_outorga(data: OutorgaIn, db: Db, user: CurrentUser):
    ensure_property(db, data.property_id, user)
    values = data.model_dump(exclude={"demands"})
    values["state"] = values["state"].upper()
    outorga = Outorga(**values)
    outorga.demands = [MonthlyDemand(**d.model_dump()) for d in data.demands]
    db.add(outorga); db.commit(); db.refresh(outorga)
    return outorga


@app.get("/outorgas/{outorga_id}", response_model=OutorgaOut)
def get_outorga(outorga_id: int, db: Db, user: CurrentUser):
    outorga = ensure_outorga(db, outorga_id, user)
    return db.scalar(select(Outorga).options(selectinload(Outorga.demands)).where(Outorga.id == outorga.id))


@app.get("/outorgas/{outorga_id}/monthly-demands", response_model=list[DemandOut])
def get_demands(outorga_id: int, db: Db, user: CurrentUser):
    outorga = ensure_outorga(db, outorga_id, user)
    return db.scalars(select(MonthlyDemand).where(MonthlyDemand.outorga_id == outorga.id).order_by(MonthlyDemand.month)).all()


@app.patch("/outorgas/{outorga_id}/monthly-demands/{month}", response_model=DemandOut)
def patch_demand(outorga_id: int, month: int, data: DemandPatch, db: Db, user: CurrentUser):
    outorga = ensure_outorga(db, outorga_id, user)
    demand = db.scalar(select(MonthlyDemand).where(MonthlyDemand.outorga_id == outorga.id, MonthlyDemand.month == month))
    if not demand: raise HTTPException(status_code=404, detail="Demanda mensal não encontrada")
    if data.max_flow_m3_h == 0 and (data.daily_hours or data.authorized_days or data.monthly_volume_m3):
        raise HTTPException(status_code=422, detail="Vazão zero exige horas, dias e volume zero")
    if data.monthly_volume_m3 != data.max_flow_m3_h * data.daily_hours * data.authorized_days:
        raise HTTPException(status_code=422, detail="Volume mensal deve ser igual a vazão × horas × dias autorizados")
    previous = {k: str(getattr(demand, k)) for k in ("max_flow_m3_h", "daily_hours", "authorized_days", "monthly_volume_m3")}
    corrected = {k: str(v) for k, v in data.model_dump().items()}
    db.add(DemandRevision(demand_id=demand.id, user_id=user.id, previous_values=previous, corrected_values=corrected))
    for key, value in data.model_dump().items(): setattr(demand, key, value)
    db.commit(); db.refresh(demand)
    return demand


@app.get("/outorgas/{outorga_id}/monthly-demands/{month}/history")
def demand_history(outorga_id: int, month: int, db: Db, user: CurrentUser):
    outorga = ensure_outorga(db, outorga_id, user)
    demand = db.scalar(select(MonthlyDemand).where(MonthlyDemand.outorga_id == outorga.id, MonthlyDemand.month == month))
    if not demand: raise HTTPException(status_code=404, detail="Demanda mensal não encontrada")
    revisions = db.scalars(select(DemandRevision).where(DemandRevision.demand_id == demand.id).order_by(DemandRevision.created_at.desc())).all()
    return [{"id": revision.id, "user_id": revision.user_id, "previous_values": revision.previous_values, "corrected_values": revision.corrected_values, "created_at": revision.created_at} for revision in revisions]


@app.get("/hydrometers", response_model=list[HydrometerOut])
def list_hydrometers(db: Db, user: CurrentUser, property_id: int | None = None):
    stmt = select(Hydrometer).join(Reservoir).join(Property).order_by(Hydrometer.id)
    if user.role != "admin": stmt = stmt.where(Property.owner_id == user.id)
    if property_id is not None:
        ensure_property(db, property_id, user); stmt = stmt.where(Property.id == property_id)
    return db.scalars(stmt).all()


@app.post("/hydrometers", status_code=201, response_model=HydrometerOut)
def create_hydrometer(data: HydrometerIn, db: Db, user: CurrentUser):
    reservoir = ensure_reservoir(db, data.reservoir_id, user)
    if data.outorga_id is not None:
        outorga = ensure_outorga(db, data.outorga_id, user)
        if outorga.property_id != reservoir.property_id: raise HTTPException(status_code=422, detail="Outorga e hidrômetro devem pertencer à mesma propriedade")
    if data.kind == "saída" and data.outorga_id is not None:
        raise HTTPException(status_code=422, detail="Hidrômetro de saída não recebe comparação de outorga")
    meter = Hydrometer(**data.model_dump()); db.add(meter); db.commit(); db.refresh(meter)
    return meter


@app.patch("/hydrometers/{hydrometer_id}/outorga/{outorga_id}", response_model=HydrometerOut)
def link_hydrometer_outorga(hydrometer_id: int, outorga_id: int, db: Db, user: CurrentUser):
    meter = db.get(Hydrometer, hydrometer_id)
    if not meter: raise HTTPException(status_code=404, detail="Hidrômetro não encontrado")
    reservoir = ensure_reservoir(db, meter.reservoir_id, user); outorga = ensure_outorga(db, outorga_id, user)
    if meter.kind != "entrada" or outorga.property_id != reservoir.property_id:
        raise HTTPException(status_code=422, detail="Somente hidrômetro de entrada pode ser vinculado à outorga da mesma propriedade")
    meter.outorga_id = outorga.id; db.commit(); db.refresh(meter); return meter


@app.get("/hydrometers/{hydrometer_id}/readings", response_model=list[HydrometerReadingOut])
def list_hydrometer_readings(hydrometer_id: int, db: Db, user: CurrentUser, skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500)):
    meter = db.get(Hydrometer, hydrometer_id)
    if not meter: raise HTTPException(status_code=404, detail="Hidrômetro não encontrado")
    ensure_reservoir(db, meter.reservoir_id, user)
    return db.scalars(select(HydrometerReading).where(HydrometerReading.hydrometer_id == meter.id).order_by(HydrometerReading.observed_at.desc()).offset(skip).limit(limit)).all()


@app.post("/hydrometers/{hydrometer_id}/readings", status_code=201, response_model=HydrometerReadingOut)
def create_hydrometer_reading(hydrometer_id: int, data: HydrometerReadingIn, db: Db, user: CurrentUser, response: Response):
    meter = db.get(Hydrometer, hydrometer_id)
    if not meter: raise HTTPException(status_code=404, detail="Hidrômetro não encontrado")
    ensure_reservoir(db, meter.reservoir_id, user)
    if data.external_id:
        old = db.scalar(select(HydrometerReading).where(HydrometerReading.hydrometer_id == meter.id, HydrometerReading.external_id == data.external_id))
        if old:
            old_time = old.observed_at if old.observed_at.tzinfo else old.observed_at.replace(tzinfo=timezone.utc)
            if old_time.astimezone(timezone.utc) != data.observed_at.astimezone(timezone.utc) or old.raw_totalizer_m3 != data.raw_totalizer_m3 or (data.volume_m3 is not None and old.volume_m3 != data.volume_m3) or old.flow_m3_h != data.flow_m3_h or old.source != data.source:
                raise HTTPException(status_code=409, detail="Identificador externo já usado por leitura diferente")
            response.status_code = 200
            return old
    old_at = db.scalar(select(HydrometerReading).where(HydrometerReading.hydrometer_id == meter.id, HydrometerReading.observed_at == data.observed_at))
    if old_at:
        if (data.volume_m3 is None or old_at.volume_m3 == data.volume_m3) and old_at.raw_totalizer_m3 == data.raw_totalizer_m3 and old_at.flow_m3_h == data.flow_m3_h and old_at.source == data.source:
            response.status_code = 200
            return old_at
        raise HTTPException(status_code=409, detail="Já existe uma leitura deste hidrômetro nesse instante observado")
    volume = data.volume_m3
    quality = data.quality
    if data.raw_totalizer_m3 is not None:
        later = db.scalar(select(HydrometerReading.id).where(HydrometerReading.hydrometer_id == meter.id, HydrometerReading.raw_totalizer_m3.is_not(None), HydrometerReading.observed_at > data.observed_at).limit(1))
        if later:
            raise HTTPException(status_code=409, detail="Leitura histórica de totalizador exige revisão das leituras posteriores")
        previous = db.scalar(select(HydrometerReading).where(HydrometerReading.hydrometer_id == meter.id, HydrometerReading.raw_totalizer_m3.is_not(None), HydrometerReading.observed_at < data.observed_at).order_by(HydrometerReading.observed_at.desc()).limit(1))
        if previous is None:
            volume = None; quality = "pendente: linha de base do totalizador; volume do intervalo indisponível"
        else:
            delta = data.raw_totalizer_m3 - previous.raw_totalizer_m3
            if delta < 0:
                volume = None; quality = "inconsistente: totalizador reiniciado ou equipamento trocado; conferir manualmente"
            elif previous.quality.startswith(("inconsistente", "pendente: totalizador anterior")):
                volume = None; quality = "pendente: totalizador anterior exige revisão; intervalo indisponível"
            else:
                volume = delta
    if meter.kind == "entrada" and not quality.startswith(("inconsistente", "pendente")):
        if meter.outorga_id is None:
            quality = "pendente: hidrômetro de entrada sem outorga associada"
        else:
            permit = db.get(Outorga, meter.outorga_id)
            observed_day = data.observed_at.astimezone(ZoneInfo("America/Sao_Paulo")).date()
            if not permit or not (permit.valid_from <= observed_day <= permit.valid_until):
                quality = "pendente: leitura fora da vigência da outorga associada"
    reading = HydrometerReading(hydrometer_id=meter.id, flow_m3_h=data.flow_m3_h, volume_m3=volume, observed_at=data.observed_at,
                                source=data.source, external_id=data.external_id, quality=quality, raw_totalizer_m3=data.raw_totalizer_m3)
    db.add(reading)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Leitura duplicada")
    db.refresh(reading); return reading


@app.get("/level-stations", response_model=list[LevelStationOut])
def list_stations(db: Db, user: CurrentUser, property_id: int | None = None):
    stmt = select(LevelStation).join(Reservoir).join(Property).order_by(LevelStation.id)
    if user.role != "admin": stmt = stmt.where(Property.owner_id == user.id)
    if property_id is not None:
        ensure_property(db, property_id, user); stmt = stmt.where(Property.id == property_id)
    return db.scalars(stmt).all()


@app.post("/level-stations", status_code=201, response_model=LevelStationOut)
def create_station(data: LevelStationIn, db: Db, user: CurrentUser):
    reservoir = ensure_reservoir(db, data.reservoir_id, user)
    if data.maximum_m > reservoir.height_m:
        raise HTTPException(status_code=422, detail="Faixa do sensor excede a altura do reservatório")
    station = LevelStation(**data.model_dump()); db.add(station)
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail="Reservatório já possui uma estação de nível")
    db.refresh(station); return station


def station_has_history(db: Session, station_id: int) -> bool:
    return bool(db.scalar(select(LevelReading.id).where(LevelReading.station_id == station_id).limit(1)) or
                db.scalar(select(LevelImageReview.id).where(LevelImageReview.station_id == station_id).limit(1)))


def lock_station_for_write(db: Session, station_id: int, user: User) -> LevelStation:
    ensure_level_station(db, station_id, user)
    station = db.scalar(select(LevelStation).where(LevelStation.id == station_id).with_for_update().execution_options(populate_existing=True))
    if not station:
        raise HTTPException(status_code=404, detail="Estação não encontrada")
    return station


@app.patch("/level-stations/{station_id}", response_model=LevelStationOut)
def update_station(station_id: int, data: LevelStationUpdate, db: Db, user: CurrentUser):
    station = lock_station_for_write(db, station_id, user)
    reservoir = ensure_reservoir(db, station.reservoir_id, user)
    if data.maximum_m > reservoir.height_m:
        raise HTTPException(status_code=422, detail="Faixa do sensor excede a altura do reservatório")
    if (data.minimum_m != station.minimum_m or data.maximum_m != station.maximum_m) and station_has_history(db, station.id):
        raise HTTPException(status_code=409, detail="A faixa não pode ser alterada porque a estação possui leituras ou imagens registradas.")
    station.name = data.name
    station.minimum_m = data.minimum_m
    station.maximum_m = data.maximum_m
    db.commit(); db.refresh(station)
    return station


@app.delete("/level-stations/{station_id}", status_code=204)
def delete_station(station_id: int, db: Db, user: CurrentUser):
    station = lock_station_for_write(db, station_id, user)
    if station_has_history(db, station.id):
        raise HTTPException(status_code=409, detail="Esta estação possui leituras ou imagens e não pode ser excluída para preservar o histórico.")
    db.delete(station); db.commit()
    return Response(status_code=204)


@app.get("/level-stations/{station_id}/readings", response_model=list[LevelReadingOut])
def list_level_readings(station_id: int, db: Db, user: CurrentUser, skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500)):
    station = db.get(LevelStation, station_id)
    if not station: raise HTTPException(status_code=404, detail="Estação não encontrada")
    ensure_reservoir(db, station.reservoir_id, user)
    return db.scalars(select(LevelReading).where(LevelReading.station_id == station.id).order_by(LevelReading.observed_at.desc()).offset(skip).limit(limit)).all()


@app.post("/level-stations/{station_id}/readings", status_code=201, response_model=LevelReadingOut)
def create_level_reading(station_id: int, data: LevelReadingIn, db: Db, user: CurrentUser):
    station = lock_station_for_write(db, station_id, user)
    reservoir = ensure_reservoir(db, station.reservoir_id, user)
    if data.level_m < station.minimum_m or data.level_m > min(station.maximum_m, reservoir.height_m):
        raise HTTPException(status_code=422, detail="Nível fora da faixa do sensor/reservatório")
    reading = LevelReading(station_id=station.id, **data.model_dump()); db.add(reading); db.commit(); db.refresh(reading); return reading


def level_image_review_values(review: LevelImageReview) -> dict:
    return {
        "status": review.status,
        "suggested_level_m": str(review.suggested_level_m) if review.suggested_level_m is not None else None,
        "confirmed_level_m": str(review.confirmed_level_m) if review.confirmed_level_m is not None else None,
        "method": review.method,
        "inconclusive_reason": review.inconclusive_reason,
        "calibration": review.calibration,
    }


@app.post("/level-stations/{station_id}/image-reviews", status_code=201, response_model=LevelImageReviewOut)
def upload_level_image(
    station_id: int,
    db: Db,
    user: CurrentUser,
    file: UploadFile = File(...),
    captured_at: datetime = Form(...),
):
    station = ensure_level_station(db, station_id, user)
    reservoir = ensure_reservoir(db, station.reservoir_id, user)
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise HTTPException(status_code=422, detail="Informe data e hora de captura com fuso horÃ¡rio.")
    payload = file.file.read(settings.ruler_image_max_bytes + 1)
    try:
        analysis = validate_and_analyze_image(
            payload,
            file.content_type,
            max_bytes=settings.ruler_image_max_bytes,
            max_pixels=settings.ruler_image_max_pixels,
        )
    except RulerImageError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    root = private_media_root()
    stored_path = None
    try:
        storage_key = persist_original(payload, root, analysis.image_format)
        stored_path = resolve_private_image(root, storage_key)
        review = LevelImageReview(
            property_id=reservoir.property_id,
            station_id=station.id,
            uploaded_by_id=user.id,
            storage_key=storage_key,
            original_name=sanitize_original_filename(file.filename),
            content_type=analysis.content_type,
            size_bytes=len(payload),
            width_px=analysis.width,
            height_px=analysis.height,
            captured_at=captured_at,
            status="inconclusive",
            method=analysis.method,
            inconclusive_reason=analysis.reason,
            analysis_details=analysis.analysis_details,
        )
        db.add(review)
        db.flush()
        append_level_image_revision(db, review, user, "uploaded", {}, {
            "status": review.status,
            "captured_at": captured_at.isoformat(),
            "unit": review.unit,
            "method": review.method,
            "inconclusive_reason": review.inconclusive_reason,
            "original_name": review.original_name,
        })
        db.commit()
        db.refresh(review)
        return review
    except Exception:
        db.rollback()
        if stored_path is not None:
            stored_path.unlink(missing_ok=True)
        raise


@app.get("/level-stations/{station_id}/image-reviews", response_model=list[LevelImageReviewOut])
def list_level_image_reviews(station_id: int, db: Db, user: CurrentUser, skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    station = ensure_level_station(db, station_id, user)
    return db.scalars(select(LevelImageReview).where(LevelImageReview.station_id == station.id).order_by(LevelImageReview.captured_at.desc()).offset(skip).limit(limit)).all()


@app.get("/level-image-reviews/{review_id}", response_model=LevelImageReviewOut)
def get_level_image_review(review_id: int, db: Db, user: CurrentUser):
    return ensure_level_image_review(db, review_id, user)


@app.get("/level-image-reviews/{review_id}/image")
def get_level_image(review_id: int, db: Db, user: CurrentUser):
    review = ensure_level_image_review(db, review_id, user)
    try:
        path = resolve_private_image(private_media_root(), review.storage_key)
    except RulerImageError:
        raise HTTPException(status_code=404, detail="Imagem nÃ£o encontrada")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Imagem nÃ£o encontrada")
    return FileResponse(path, media_type=review.content_type, filename=review.original_name, headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})


@app.post("/level-image-reviews/{review_id}/suggestion", response_model=LevelImageReviewOut)
def suggest_level_image_value(review_id: int, data: LevelImageSuggestionIn, db: Db, user: CurrentUser):
    review = ensure_level_image_review(db, review_id, user)
    station = ensure_level_station(db, review.station_id, user)
    reservoir = ensure_reservoir(db, station.reservoir_id, user)
    if data.level_m < station.minimum_m or data.level_m > min(station.maximum_m, reservoir.height_m):
        raise HTTPException(status_code=422, detail="NÃ­vel informado fora da faixa fÃ­sica da estaÃ§Ã£o/reservatÃ³rio.")
    previous = level_image_review_values(review)
    mark_image_review_pending(review, db)
    review.suggested_level_m = data.level_m
    review.method = "manual_entry"
    review.inconclusive_reason = None
    review.calibration = None
    append_level_image_revision(db, review, user, "manual_suggestion", previous, level_image_review_values(review))
    db.commit(); db.refresh(review)
    return review


@app.post("/level-image-reviews/{review_id}/calibrate", response_model=LevelImageReviewOut)
def calibrate_level_image(review_id: int, data: RulerCalibrationIn, db: Db, user: CurrentUser):
    review = ensure_level_image_review(db, review_id, user)
    station = ensure_level_station(db, review.station_id, user)
    reservoir = ensure_reservoir(db, station.reservoir_id, user)
    try:
        result = calibrated_level(
            width=review.width_px,
            height=review.height_px,
            reference_1=data.reference_1.model_dump(),
            reference_2=data.reference_2.model_dump(),
            waterline=data.waterline.model_dump(),
            minimum_m=station.minimum_m,
            maximum_m=min(station.maximum_m, reservoir.height_m),
        )
    except RulerImageError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    previous = level_image_review_values(review)
    calibration = {
        "reference_1": {key: str(value) for key, value in data.reference_1.model_dump().items()},
        "reference_2": {key: str(value) for key, value in data.reference_2.model_dump().items()},
        "waterline": {key: str(value) for key, value in data.waterline.model_dump().items()},
        "interpolation": "linear_y_between_two_reviewer-selected_marks_on_this_image",
    }
    mark_image_review_pending(review, db)
    review.suggested_level_m = result
    review.method = "reviewer_selected_individual_calibration"
    review.inconclusive_reason = None
    review.calibration = calibration
    append_level_image_revision(db, review, user, "image_calibrated", previous, level_image_review_values(review))
    db.commit(); db.refresh(review)
    return review


@app.post("/level-image-reviews/{review_id}/confirm", response_model=LevelImageConfirmationOut)
def confirm_level_image(review_id: int, data: LevelImageSuggestionIn, db: Db, user: CurrentUser):
    review = ensure_level_image_review(db, review_id, user)
    if review.status != "pending_review":
        raise HTTPException(status_code=409, detail="Registre uma sugestÃ£o calibrada ou manual antes de confirmar a leitura.")
    station = ensure_level_station(db, review.station_id, user)
    reservoir = ensure_reservoir(db, station.reservoir_id, user)
    if data.level_m < station.minimum_m or data.level_m > min(station.maximum_m, reservoir.height_m):
        raise HTTPException(status_code=422, detail="NÃ­vel confirmado fora da faixa fÃ­sica da estaÃ§Ã£o/reservatÃ³rio.")
    previous = level_image_review_values(review)
    old_reading = db.scalar(select(LevelReading).where(LevelReading.image_review_id == review.id))
    if old_reading is None:
        reading = LevelReading(
            station_id=station.id,
            level_m=data.level_m,
            observed_at=review.captured_at,
            source="imagem_revisada",
            quality="revisada por usuÃ¡rio; evidÃªncia fotogrÃ¡fica associada",
            image_review_id=review.id,
        )
        db.add(reading)
    else:
        reading = old_reading
        reading.level_m = data.level_m
        reading.observed_at = review.captured_at
        reading.source = "imagem_revisada"
        reading.quality = "revisada por usuÃ¡rio; evidÃªncia fotogrÃ¡fica associada"
    review.status = "confirmed"
    review.confirmed_level_m = data.level_m
    review.reviewed_by_id = user.id
    review.reviewed_at = datetime.now(timezone.utc)
    corrected = level_image_review_values(review)
    corrected["reading_level_m"] = str(data.level_m)
    append_level_image_revision(db, review, user, "confirmed_or_corrected", previous, corrected)
    db.commit(); db.refresh(review); db.refresh(reading)
    return {"review": review, "reading": reading}


@app.get("/level-image-reviews/{review_id}/history", response_model=list[LevelImageReviewRevisionOut])
def level_image_review_history(review_id: int, db: Db, user: CurrentUser):
    review = ensure_level_image_review(db, review_id, user)
    return db.scalars(select(LevelImageReviewRevision).where(LevelImageReviewRevision.review_id == review.id).order_by(LevelImageReviewRevision.created_at, LevelImageReviewRevision.id)).all()


@app.post("/energy/tariffs", status_code=201, response_model=TariffOut)
def create_tariff(data: TariffIn, db: Db, user: CurrentUser):
    ensure_property(db, data.property_id, user)
    tariff = EnergyTariff(**data.model_dump()); db.add(tariff); db.commit(); db.refresh(tariff); return tariff


@app.get("/energy/tariffs/{property_id}", response_model=list[TariffOut])
def list_tariffs(property_id: int, db: Db, user: CurrentUser):
    ensure_property(db, property_id, user)
    return db.scalars(select(EnergyTariff).where(EnergyTariff.property_id == property_id).order_by(EnergyTariff.valid_from.desc())).all()


@app.get("/energy/estimate/{property_id}")
def estimate_energy(property_id: int, db: Db, user: CurrentUser, start: date | None = None, end: date | None = None):
    ensure_property(db, property_id, user)
    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date(); start = start or today.replace(day=1); end = end or today
    if end < start: raise HTTPException(status_code=422, detail="Intervalo inválido")
    meters = list(db.scalars(select(Hydrometer).join(Reservoir).where(Reservoir.property_id == property_id).order_by(Hydrometer.id)))
    readings = {}
    for meter in meters:
        readings[meter.id] = db.scalars(select(HydrometerReading).where(HydrometerReading.hydrometer_id == meter.id, HydrometerReading.observed_at >= datetime.combine(start, time.min, ZoneInfo("America/Sao_Paulo")).astimezone(timezone.utc), HydrometerReading.observed_at < datetime.combine(end + timedelta(days=1), time.min, ZoneInfo("America/Sao_Paulo")).astimezone(timezone.utc))).all()
    tariff_row = db.scalar(select(EnergyTariff).where(EnergyTariff.property_id == property_id, EnergyTariff.valid_from <= start, (EnergyTariff.valid_until.is_(None) | (EnergyTariff.valid_until >= end))).order_by(EnergyTariff.valid_from.desc()).limit(1))
    result = energy_estimate([m for m in meters if m.kind == "entrada"], {m.id: readings[m.id] for m in meters if m.kind == "entrada"}, tariff_row.value_brl_kwh if tariff_row else None)
    result.update({"property_id": property_id, "period": {"start": start.isoformat(), "end": end.isoformat()}, "tariff": tariff_row})
    return result


@app.get("/evaporation/estimate/{property_id}")
def estimate_evaporation(property_id: int, db: Db, user: CurrentUser):
    prop = ensure_property(db, property_id, user)
    if is_demo_property(settings, user, prop):
        reservoir = db.scalar(select(Reservoir).where(Reservoir.property_id == property_id).order_by(Reservoir.id))
        if reservoir:
            return demo_balance(reservoir.id)
    return water_balance(area_m2=None, duration_days=None, rain_mm=None, inflow_m3=None, outflow_m3=None, other_outflow_m3=None, initial_volume_m3=None, final_volume_m3=None)


@app.get("/alerts/{property_id}", response_model=list[AlertOut])
def get_alerts(property_id: int, db: Db, user: CurrentUser, status_filter: str | None = Query(default=None, alias="status", pattern="^(open|resolved)$"), skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    ensure_property(db, property_id, user)
    stmt = select(Alert).where(Alert.property_id == property_id).order_by(Alert.occurred_at.desc()).offset(skip).limit(limit)
    if status_filter:
        stmt = stmt.where(Alert.status == status_filter)
    return db.scalars(stmt).all()


@app.post("/alerts/{property_id}/evaluate", response_model=AlertEvaluationOut)
def evaluate_property_alerts(property_id: int, db: Db, user: CurrentUser):
    ensure_property(db, property_id, user)
    now = datetime.now(ZoneInfo("America/Sao_Paulo"))
    today = now.date()
    candidates: dict[str, dict] = {}
    threshold = settings.alert_stale_after_hours

    for meter in db.scalars(select(Hydrometer).join(Reservoir).where(Reservoir.property_id == property_id).order_by(Hydrometer.id)).all():
        latest = db.scalar(select(HydrometerReading).where(HydrometerReading.hydrometer_id == meter.id, ~HydrometerReading.quality.like("inconsistente%")).order_by(HydrometerReading.observed_at.desc()).limit(1))
        stale = stale_measurement_candidate("hidrômetro", meter.id, meter.name, latest.observed_at if latest else None, meter.created_at, now, threshold)
        if stale:
            candidates[stale["fingerprint"]] = stale
        pending = missing_outorga_candidate(meter)
        if pending:
            candidates[pending["fingerprint"]] = pending
        pending_quality = HydrometerReading.quality.like("pendente%") | HydrometerReading.quality.like("inconsistente%")
        for reading in db.scalars(select(HydrometerReading).where(HydrometerReading.hydrometer_id == meter.id, pending_quality).order_by(HydrometerReading.observed_at.desc())).all():
            review = quality_review_candidate(meter, reading)
            if review:
                candidates[review["fingerprint"]] = review

    for station in db.scalars(select(LevelStation).join(Reservoir).where(Reservoir.property_id == property_id).order_by(LevelStation.id)).all():
        latest_level = db.scalar(select(LevelReading).where(LevelReading.station_id == station.id, ~LevelReading.quality.like("inconsistente%"), ~LevelReading.quality.like("inconclusiva%")).order_by(LevelReading.observed_at.desc()).limit(1))
        stale = stale_measurement_candidate("nível", station.id, station.name, latest_level.observed_at if latest_level else None, station.created_at, now, threshold)
        if stale:
            candidates[stale["fingerprint"]] = stale
        pending_level_quality = LevelReading.quality.like("pendente%") | LevelReading.quality.like("inconsistente%") | LevelReading.quality.like("inconclusiva%")
        for reading in db.scalars(select(LevelReading).where(LevelReading.station_id == station.id, pending_level_quality).order_by(LevelReading.observed_at.desc())).all():
            review = level_quality_review_candidate(station, reading)
            if review:
                candidates[review["fingerprint"]] = review

    for image_review in db.scalars(select(LevelImageReview).where(LevelImageReview.property_id == property_id, LevelImageReview.status.in_(("inconclusive", "pending_review")))).all():
        fingerprint = f"image-review:{image_review.id}"
        candidates[fingerprint] = {
            "fingerprint": fingerprint, "origin": "imagem de régua", "rule": "Imagem pendente de revisão", "severity": "warning",
            "details": {"review_id": image_review.id, "station_id": image_review.station_id, "captured_at": image_review.captured_at.isoformat(), "status": image_review.status, "message": "Confira a imagem e confirme uma leitura válida."},
        }

    permits = db.scalars(select(Outorga).options(selectinload(Outorga.demands)).where(Outorga.property_id == property_id).order_by(Outorga.id)).all()
    for permit in permits:
        expired = expired_outorga_candidate(permit, today)
        if expired:
            candidates[expired["fingerprint"]] = expired
        demand = next((d for d in permit.demands if d.month == today.month), None)
        if not demand:
            continue
        meter_ids = db.scalars(select(Hydrometer.id).where(Hydrometer.outorga_id == permit.id, Hydrometer.kind == "entrada")).all()
        start = datetime.combine(today.replace(day=1), time.min, ZoneInfo("America/Sao_Paulo")).astimezone(timezone.utc)
        end = datetime.combine(today + timedelta(days=1), time.min, ZoneInfo("America/Sao_Paulo")).astimezone(timezone.utc)
        readings = db.scalars(select(HydrometerReading).where(HydrometerReading.hydrometer_id.in_(meter_ids) if meter_ids else False, HydrometerReading.observed_at >= start, HydrometerReading.observed_at < end).order_by(HydrometerReading.observed_at)).all()
        for candidate in daily_extrapolation_candidates(permit, demand, readings, today.year, today.month):
            candidates[candidate["fingerprint"]] = candidate

    created = 0
    reopened = 0
    automatically_resolved = 0
    for fingerprint, candidate in candidates.items():
        alert = db.scalar(select(Alert).where(Alert.fingerprint == fingerprint))
        if alert is None:
            db.add(Alert(property_id=property_id, fingerprint=fingerprint, origin=candidate["origin"], rule=candidate["rule"], details=candidate["details"], occurred_at=now, severity=candidate["severity"], status="open", resolution_history=[]))
            created += 1
        elif alert.status == "resolved":
            history = list(alert.resolution_history or [])
            history.append({"event": "reopened", "at": now.isoformat(), "user_id": user.id, "reason": "A condição foi encontrada novamente."})
            alert.resolution_history = history
            alert.status = "open"
            alert.resolved_at = None
            alert.resolved_by_id = None
            alert.details = candidate["details"]
            alert.severity = candidate["severity"]
            reopened += 1
        else:
            alert.details = candidate["details"]
            alert.severity = candidate["severity"]

    active_fingerprints = set(candidates)
    reconcilable_prefixes = ("stale:", "missing-outorga:", "expired-outorga:", "reading-review:", "image-review:")
    open_alerts = db.scalars(select(Alert).where(Alert.property_id == property_id, Alert.status == "open")).all()
    for alert in open_alerts:
        if not alert.fingerprint.startswith(reconcilable_prefixes) or alert.fingerprint in active_fingerprints:
            continue
        history = list(alert.resolution_history or [])
        history.append({"event": "resolved_automatically", "at": now.isoformat(), "user_id": user.id, "reason": "A condição monitorada não apareceu na avaliação atual."})
        alert.resolution_history = history
        alert.status = "resolved"
        alert.resolved_at = now
        alert.resolved_by_id = user.id
        automatically_resolved += 1

    db.commit()
    active_count = len(db.scalars(select(Alert.id).where(Alert.property_id == property_id, Alert.status == "open")).all())
    result_alerts = db.scalars(select(Alert).where(Alert.property_id == property_id).order_by(Alert.occurred_at.desc()).limit(100)).all()
    return {"created": created, "reopened": reopened, "automatically_resolved": automatically_resolved, "active": active_count, "alerts": result_alerts}


@app.post("/alerts/{alert_id}/resolve", response_model=AlertOut)
def resolve_alert(alert_id: int, data: AlertResolveIn, db: Db, user: CurrentUser):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    ensure_property(db, alert.property_id, user)
    if alert.status == "open":
        now = datetime.now(ZoneInfo("America/Sao_Paulo"))
        history = list(alert.resolution_history or [])
        history.append({"event": "resolved", "at": now.isoformat(), "user_id": user.id, "note": data.note})
        alert.resolution_history = history
        alert.status = "resolved"
        alert.resolved_at = now
        alert.resolved_by_id = user.id
        db.commit()
        db.refresh(alert)
    return alert


@app.get("/dashboard/{property_id}")
def dashboard(property_id: int, db: Db, user: CurrentUser):
    prop = ensure_property(db, property_id, user)
    reservoirs = list(db.scalars(select(Reservoir).options(selectinload(Reservoir.hydrometers), selectinload(Reservoir.level_station)).where(Reservoir.property_id == property_id).order_by(Reservoir.id)))
    permits = list(db.scalars(select(Outorga).options(selectinload(Outorga.demands)).where(Outorga.property_id == property_id).order_by(Outorga.id)))
    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    permit_summaries = []
    recent_meters = []
    latest_levels = []
    for permit in permits:
        demand = next((d for d in permit.demands if d.month == today.month), None)
        if demand:
            meter_ids = db.scalars(select(Hydrometer.id).where(Hydrometer.outorga_id == permit.id, Hydrometer.kind == "entrada")).all()
            readings = db.scalars(select(HydrometerReading).where(HydrometerReading.hydrometer_id.in_(meter_ids) if meter_ids else False, HydrometerReading.observed_at >= datetime.combine(today.replace(day=1), time.min, ZoneInfo("America/Sao_Paulo")).astimezone(timezone.utc), HydrometerReading.observed_at < datetime.combine(today + timedelta(days=1), time.min, ZoneInfo("America/Sao_Paulo")).astimezone(timezone.utc)).order_by(HydrometerReading.observed_at)).all()
            summary = demo_permit_comparison(permit, demand, today) if is_demo_property(settings, user, prop) and permit.is_demo else compare_month(permit, demand, readings, today.year, today.month)
            permit_summaries.append({"outorga_id": permit.id, "name": permit.name, "validity_status": "vigente" if permit.valid_from <= today <= permit.valid_until else "fora da vigência", **summary})
    for reservoir in reservoirs:
        for meter in reservoir.hydrometers:
            recent = db.scalars(select(HydrometerReading).where(HydrometerReading.hydrometer_id == meter.id).order_by(HydrometerReading.observed_at.desc()).limit(5)).all()
            recent_meters.append({"hydrometer": meter, "readings": recent})
        if reservoir.level_station:
            reading = db.scalar(select(LevelReading).where(LevelReading.station_id == reservoir.level_station.id).order_by(LevelReading.observed_at.desc()).limit(1))
            volume = None
            if reading:
                try: volume = reservoir_volume(reservoir.base_width_m, reservoir.base_length_m, reservoir.top_width_m, reservoir.top_length_m, reservoir.height_m, reading.level_m)
                except ValueError: volume = None
            latest_levels.append({"reservoir_id": reservoir.id, "reservoir_name": reservoir.name, "station": reservoir.level_station, "latest": reading, "volume_m3": volume, "volume_status": "calculado pela geometria retangular inclinada" if volume is not None else "indisponível"})
        else:
            latest_levels.append({"reservoir_id": reservoir.id, "reservoir_name": reservoir.name, "station": None, "latest": None, "volume_m3": None, "volume_status": "estação sem cadastro"})
    return {
        "property": {"id": prop.id, "name": prop.name, "cep": prop.cep, "city": prop.city, "state": prop.state, "has_boundary": bool(prop.boundary_kml)},
        "reservoirs": [{"id": r.id, "property_id": r.property_id, "name": r.name, "base_width_m": r.base_width_m, "base_length_m": r.base_length_m, "top_width_m": r.top_width_m, "top_length_m": r.top_length_m, "height_m": r.height_m, "geometry_assumption": r.geometry_assumption} for r in reservoirs],
        "outorgas": [{"id": o.id, "name": o.name, "permit_number": o.permit_number, "valid_from": o.valid_from, "valid_until": o.valid_until, "is_demo": o.is_demo} for o in permits],
        "monthly_comparisons": permit_summaries,
        "latest_levels": [{
            "reservoir_id": item["reservoir_id"], "reservoir_name": item["reservoir_name"],
            "station": None if item["station"] is None else {"id": item["station"].id, "reservoir_id": item["station"].reservoir_id, "name": item["station"].name, "minimum_m": item["station"].minimum_m, "maximum_m": item["station"].maximum_m},
            "latest": None if item["latest"] is None else {"id": item["latest"].id, "station_id": item["latest"].station_id, "level_m": item["latest"].level_m, "observed_at": item["latest"].observed_at, "created_at": item["latest"].created_at, "source": item["latest"].source, "quality": item["latest"].quality},
            "volume_m3": item["volume_m3"], "volume_status": item["volume_status"],
        } for item in latest_levels],
        "recent_hydrometers": [{"hydrometer": {"id": item["hydrometer"].id, "reservoir_id": item["hydrometer"].reservoir_id, "outorga_id": item["hydrometer"].outorga_id, "name": item["hydrometer"].name, "kind": item["hydrometer"].kind, "rated_power_kw": item["hydrometer"].rated_power_kw, "rated_power_cv": item["hydrometer"].rated_power_cv, "is_demo": item["hydrometer"].is_demo}, "readings": [{"id": r.id, "volume_m3": r.volume_m3, "flow_m3_h": r.flow_m3_h, "observed_at": r.observed_at, "created_at": r.created_at, "source": r.source, "quality": r.quality} for r in item["readings"]]} for item in recent_meters],
        "evaporation": {"status": "dados insuficientes", "message": "Informe área superficial, precipitação, níveis e fluxos do mesmo intervalo para calcular o balanço."},
        "coverage": "incompleto até haver cobertura diária registrada", "updated_at": datetime.now(timezone.utc),
    }
