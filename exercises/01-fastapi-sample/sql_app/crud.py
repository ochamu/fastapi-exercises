from sqlalchemy.orm import Session

from . import auth, models, schemas


def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()


def get_user_by_token(db: Session, token: str):
    token_hash = auth.hash_token(token)
    return (
        db.query(models.User)
        .filter(models.User.api_token_hash == token_hash)
        .first()
    )


def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()


def create_user(db: Session, user: schemas.UserCreate):
    fake_hashed_password = user.password + "notreallyhashed"
    api_token = auth.generate_api_token()
    token_hash = auth.hash_token(api_token)
    db_user = models.User(
        email=user.email,
        hashed_password=fake_hashed_password,
        api_token_hash=token_hash,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    db_user.api_token = api_token
    return db_user


def get_items(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Item).offset(skip).limit(limit).all()


def get_items_by_owner(
    db: Session, owner_id: int, skip: int = 0, limit: int = 100
):
    return (
        db.query(models.Item)
        .filter(models.Item.owner_id == owner_id)
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_user_item(db: Session, item: schemas.ItemCreate, user_id: int):
    db_item = models.Item(**item.dict(), owner_id=user_id)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def deactivate_user_and_transfer_items(db: Session, user_id: int):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        return {"status": "not_found", "user": None}
    if not user.is_active:
        return {"status": "already_inactive", "user": user}

    next_owner = (
        db.query(models.User)
        .filter(models.User.is_active.is_(True), models.User.id != user_id)
        .order_by(models.User.id.asc())
        .first()
    )
    if next_owner is None:
        return {"status": "no_active_successor", "user": user}

    for item in list(user.items):
        item.owner = next_owner

    user.is_active = False
    db.commit()
    db.refresh(user)
    return {"status": "deactivated", "user": user}
