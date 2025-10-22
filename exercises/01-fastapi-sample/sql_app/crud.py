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


def create_user_item(db: Session, item: schemas.ItemCreate, user_id: int):
    db_item = models.Item(**item.dict(), owner_id=user_id)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item
