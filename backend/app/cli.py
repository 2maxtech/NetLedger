import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User, UserRole


async def create_admin(username: str, email: str, password: str):
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        existing = await session.execute(select(User).where(User.username == username))
        if existing.scalar_one_or_none():
            print(f"User '{username}' already exists.")
            return

        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role=UserRole.admin,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        print(f"Admin user '{username}' created successfully.")

    await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python -m app.cli <username> <email> <password>")
        sys.exit(1)

    asyncio.run(create_admin(sys.argv[1], sys.argv[2], sys.argv[3]))
