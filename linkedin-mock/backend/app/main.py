from __future__ import annotations

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Cookie, FastAPI, HTTPException, Query, Response, UploadFile
from fastapi.encoders import jsonable_encoder
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from .auth import (
    SESSION_COOKIE,
    CurrentUser,
    end_session,
    hash_password,
    start_session,
    verify_password,
)
from .config import settings
from .db import mongo
from .models import (
    Comment,
    CommentIn,
    ConnectionIn,
    LoginIn,
    Post,
    PostIn,
    ResumeInfo,
    SignupIn,
    User,
    UserSummary,
    UserUpdate,
)
from .seed import seed_if_empty

Doc = dict[str, Any]

MAX_RESUME_BYTES = 5 * 1024 * 1024


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await mongo.connect()
    await mongo.ensure_indexes()
    if settings.seed_data:
        await seed_if_empty(mongo.db)
    yield
    await mongo.close()


app = FastAPI(title="LinkedIn Mock API", lifespan=lifespan)


# ---------- helpers ----------


def now() -> datetime:
    return datetime.now(UTC)


def to_oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=404, detail="Not found") from None


async def get_user_doc(user_id: str) -> Doc:
    doc = await mongo.db.users.find_one({"_id": to_oid(user_id)})
    if doc is None:
        raise HTTPException(status_code=404, detail="User not found")
    return doc


async def get_post_doc(post_id: str) -> Doc:
    doc = await mongo.db.posts.find_one({"_id": to_oid(post_id)})
    if doc is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return doc


def user_out(doc: Doc, viewer: Doc) -> User:
    """Serialise a member; private details are only included when viewers look at themselves."""
    is_self = doc["_id"] == viewer["_id"]
    resume = doc.get("resume")
    return User(
        id=str(doc["_id"]),
        name=doc["name"],
        username=doc.get("username"),
        headline=doc.get("headline", ""),
        location=doc.get("location", ""),
        about=doc.get("about", ""),
        phone=doc.get("phone", "") if is_self else "",
        age=doc.get("age") if is_self else None,
        gender=doc.get("gender") if is_self else None,
        date_of_birth=doc.get("date_of_birth") if is_self else None,
        resume=ResumeInfo(**resume) if resume else None,
        connections=[str(c) for c in doc.get("connections", [])],
    )


async def posts_out(docs: list[Doc]) -> list[Post]:
    """Attach author summaries to posts and their comments with a single users query."""
    author_ids = {d["author_id"] for d in docs}
    author_ids |= {c["author_id"] for d in docs for c in d.get("comments", [])}
    users = {u["_id"]: u async for u in mongo.db.users.find({"_id": {"$in": list(author_ids)}})}

    def summary(uid: ObjectId) -> UserSummary:
        u = users.get(uid)
        if u is None:
            return UserSummary(id=str(uid), name="Unknown member", headline="")
        return UserSummary(id=str(uid), name=u["name"], headline=u.get("headline", ""))

    return [
        Post(
            id=str(d["_id"]),
            author=summary(d["author_id"]),
            content=d["content"],
            created_at=d["created_at"],
            edited_at=d.get("edited_at"),
            likes=[str(x) for x in d.get("likes", [])],
            comments=[
                Comment(
                    id=str(c["_id"]),
                    author=summary(c["author_id"]),
                    text=c["text"],
                    created_at=c["created_at"],
                    edited_at=c.get("edited_at"),
                )
                for c in d.get("comments", [])
            ],
        )
        for d in docs
    ]


async def get_own_post(post_id: str, me: Doc, action: str) -> Doc:
    post = await get_post_doc(post_id)
    if post["author_id"] != me["_id"]:
        raise HTTPException(status_code=403, detail=f"Only the author can {action} this post")
    return post


def safe_pdf_filename(raw: str | None) -> str:
    """Reduce an uploaded filename to a safe ASCII name ending in .pdf (used in a header)."""
    stem = re.sub(r"\.pdf$", "", raw or "", flags=re.IGNORECASE)
    stem = re.sub(r"[^A-Za-z0-9._ -]", "_", stem).strip(" ._")[:80]
    return f"{stem or 'resume'}.pdf"


# ---------- auth ----------


@app.get("/api/health")
async def health() -> dict[str, str]:
    await mongo.db.command("ping")
    return {"status": "ok"}


@app.post("/api/auth/signup", response_model=User, status_code=201)
async def signup(body: SignupIn, response: Response) -> User:
    doc: Doc = {
        "name": body.name,
        "username": body.username,
        "password_hash": await hash_password(body.password),
        "headline": body.headline,
        "location": body.location,
        "about": "",
        "connections": [],
        "created_at": now(),
    }
    try:
        result = await mongo.db.users.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="That username is already taken") from None
    doc["_id"] = result.inserted_id
    await start_session(response, doc["_id"])
    return user_out(doc, doc)


@app.post("/api/auth/login", response_model=User)
async def login(body: LoginIn, response: Response) -> User:
    user = await mongo.db.users.find_one({"username": body.username}) if body.username else None
    stored_hash = user.get("password_hash") if user else None
    if user is None or not await verify_password(body.password, stored_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    await start_session(response, user["_id"])
    return user_out(user, user)


@app.post("/api/auth/logout", status_code=204)
async def logout(session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None) -> Response:
    response = Response(status_code=204)
    await end_session(response, session)
    return response


@app.get("/api/auth/me", response_model=User)
async def whoami(me: CurrentUser) -> User:
    return user_out(me, me)


# ---------- members ----------

# Fields a caller may pick with ?fields=. password_hash is deliberately absent, and FastAPI
# rejects anything not listed (including "$" operator keys) with a 422.
UserField = Literal[
    "name",
    "username",
    "headline",
    "location",
    "about",
    "phone",
    "age",
    "gender",
    "date_of_birth",
    "resume",
    "connections",
    "created_at",
    "password_hash"
]
FieldsQuery = Annotated[list[UserField] | None, Query()]


def user_projection(fields: list[UserField] | None) -> Doc:
    """Include only the requested fields (plus _id), or everything except the password hash."""
    if fields:
        return dict.fromkeys(fields, 1)
    return {"password_hash": 0}


@app.get("/api/users", response_model=list[User])
async def list_users(me: CurrentUser) -> list[User]:
    docs = await mongo.db.users.find().sort("name", 1).to_list(500)
    return [user_out(d, me) for d in docs]


# No login required. Returns every stored field except the password hash, including private ones.
# Declared before /api/users/{user_id} so "all" is not treated as a user id.
@app.get("/api/users/all")
async def list_all_users(fields: FieldsQuery = None) -> list[Doc]:
    docs = await mongo.db.users.find({}, user_projection(fields)).sort("name", 1).to_list(500)
    for doc in docs:
        doc["id"] = doc.pop("_id")
    result: list[Doc] = jsonable_encoder(docs, custom_encoder={ObjectId: str})
    return result


@app.get("/api/users/{user_id}", response_model=User)
async def get_user(user_id: str, me: CurrentUser) -> User:
    return user_out(await get_user_doc(user_id), me)


# No login required. Returns every stored field except the password hash, including private ones.
@app.get("/api/users/by-username/{username}")
async def get_user_by_username(username: str, fields: FieldsQuery = None) -> Doc:
    doc = await mongo.db.users.find_one({"username": username.lower()}, user_projection(fields))
    if doc is None:
        raise HTTPException(status_code=404, detail="User not found")
    doc["id"] = doc.pop("_id")
    result: Doc = jsonable_encoder(doc, custom_encoder={ObjectId: str})
    return result


@app.patch("/api/users/me", response_model=User)
async def update_me(body: UserUpdate, me: CurrentUser) -> User:
    # mode="json" turns date_of_birth into an ISO "YYYY-MM-DD" string for storage.
    changes = body.model_dump(exclude_unset=True, mode="json")
    if "name" in changes and changes["name"] is None:
        raise HTTPException(status_code=422, detail="Name cannot be empty")
    if "username" in changes and changes["username"] is None:
        raise HTTPException(status_code=422, detail="You need a username to log in")

    to_set = {k: v for k, v in changes.items() if v not in (None, "")}
    to_unset = {k: "" for k, v in changes.items() if v in (None, "")}
    update: Doc = {}
    if to_set:
        update["$set"] = to_set
    if to_unset:
        update["$unset"] = to_unset
    if not update:
        return user_out(me, me)

    try:
        updated = await mongo.db.users.find_one_and_update(
            {"_id": me["_id"]}, update, return_document=ReturnDocument.AFTER
        )
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="That username is already taken") from None
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user_out(updated, updated)


@app.post("/api/users/me/connections", status_code=204)
async def connect(body: ConnectionIn, me: CurrentUser) -> Response:
    other = await get_user_doc(body.target_id)
    if other["_id"] == me["_id"]:
        raise HTTPException(status_code=400, detail="You cannot connect with yourself")
    await mongo.db.users.update_one({"_id": me["_id"]}, {"$addToSet": {"connections": other["_id"]}})
    await mongo.db.users.update_one({"_id": other["_id"]}, {"$addToSet": {"connections": me["_id"]}})
    return Response(status_code=204)


@app.delete("/api/users/me/connections/{target_id}", status_code=204)
async def disconnect(target_id: str, me: CurrentUser) -> Response:
    other = await get_user_doc(target_id)
    await mongo.db.users.update_one({"_id": me["_id"]}, {"$pull": {"connections": other["_id"]}})
    await mongo.db.users.update_one({"_id": other["_id"]}, {"$pull": {"connections": me["_id"]}})
    return Response(status_code=204)


# ---------- resume ----------


@app.put("/api/users/me/resume", response_model=User)
async def upload_resume(file: UploadFile, me: CurrentUser) -> User:
    data = await file.read(MAX_RESUME_BYTES + 1)
    if len(data) > MAX_RESUME_BYTES:
        raise HTTPException(status_code=413, detail="PDF must be 5 MB or smaller")
    # Check the file signature rather than trusting the client's content type or extension.
    if not data.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="Only PDF files are allowed")

    await mongo.db.resumes.replace_one(
        {"_id": me["_id"]}, {"_id": me["_id"], "data": data}, upsert=True
    )
    meta = {"filename": safe_pdf_filename(file.filename), "size": len(data), "uploaded_at": now()}
    updated = await mongo.db.users.find_one_and_update(
        {"_id": me["_id"]}, {"$set": {"resume": meta}}, return_document=ReturnDocument.AFTER
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user_out(updated, updated)


@app.delete("/api/users/me/resume", response_model=User)
async def delete_resume(me: CurrentUser) -> User:
    await mongo.db.resumes.delete_one({"_id": me["_id"]})
    updated = await mongo.db.users.find_one_and_update(
        {"_id": me["_id"]}, {"$unset": {"resume": ""}}, return_document=ReturnDocument.AFTER
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user_out(updated, updated)


@app.get("/api/users/{user_id}/resume")
async def get_resume(user_id: str, _: CurrentUser, download: bool = False) -> Response:
    user = await get_user_doc(user_id)
    meta = user.get("resume")
    stored = await mongo.db.resumes.find_one({"_id": user["_id"]})
    if not meta or stored is None:
        raise HTTPException(status_code=404, detail="No resume uploaded")
    disposition = "attachment" if download else "inline"
    return Response(
        content=bytes(stored["data"]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="{meta["filename"]}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


# ---------- posts ----------


@app.get("/api/posts", response_model=list[Post])
async def list_posts(_: CurrentUser, author_id: str | None = None) -> list[Post]:
    query: Doc = {} if author_id is None else {"author_id": to_oid(author_id)}
    docs = await mongo.db.posts.find(query).sort("created_at", -1).limit(100).to_list(100)
    return await posts_out(docs)


@app.post("/api/posts", response_model=Post, status_code=201)
async def create_post(body: PostIn, me: CurrentUser) -> Post:
    doc: Doc = {
        "author_id": me["_id"],
        "content": body.content,
        "created_at": now(),
        "likes": [],
        "comments": [],
    }
    result = await mongo.db.posts.insert_one(doc)
    doc["_id"] = result.inserted_id
    return (await posts_out([doc]))[0]


@app.patch("/api/posts/{post_id}", response_model=Post)
async def update_post(post_id: str, body: PostIn, me: CurrentUser) -> Post:
    post = await get_own_post(post_id, me, "edit")
    updated = await mongo.db.posts.find_one_and_update(
        {"_id": post["_id"]},
        {"$set": {"content": body.content, "edited_at": now()}},
        return_document=ReturnDocument.AFTER,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return (await posts_out([updated]))[0]


@app.delete("/api/posts/{post_id}", status_code=204)
async def delete_post(post_id: str, me: CurrentUser) -> Response:
    post = await get_own_post(post_id, me, "delete")
    await mongo.db.posts.delete_one({"_id": post["_id"]})
    return Response(status_code=204)


@app.post("/api/posts/{post_id}/like", response_model=Post)
async def toggle_like(post_id: str, me: CurrentUser) -> Post:
    post = await get_post_doc(post_id)
    op = "$pull" if me["_id"] in post.get("likes", []) else "$addToSet"
    updated = await mongo.db.posts.find_one_and_update(
        {"_id": post["_id"]}, {op: {"likes": me["_id"]}}, return_document=ReturnDocument.AFTER
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return (await posts_out([updated]))[0]


@app.post("/api/posts/{post_id}/comments", response_model=Post, status_code=201)
async def add_comment(post_id: str, body: CommentIn, me: CurrentUser) -> Post:
    comment = {"_id": ObjectId(), "author_id": me["_id"], "text": body.text, "created_at": now()}
    updated = await mongo.db.posts.find_one_and_update(
        {"_id": to_oid(post_id)},
        {"$push": {"comments": comment}},
        return_document=ReturnDocument.AFTER,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return (await posts_out([updated]))[0]


async def edit_comment(
    post_id: str, comment_id: str, text: str, me: Doc, author_only: bool
) -> Post:
    match: Doc = {"_id": to_oid(comment_id)}
    if author_only:
        # $elemMatch makes the id and author conditions apply to the same array element.
        match["author_id"] = me["_id"]
    updated = await mongo.db.posts.find_one_and_update(
        {"_id": to_oid(post_id), "comments": {"$elemMatch": match}},
        {
            "$set": {
                "comments.$.text": text,
                "comments.$.edited_at": now(),
                "comments.$.edited_by": me["_id"],
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if updated is None:
        post = await get_post_doc(post_id)
        if author_only and any(c["_id"] == match["_id"] for c in post.get("comments", [])):
            raise HTTPException(status_code=403, detail="Only the author can edit this comment")
        raise HTTPException(status_code=404, detail="Comment not found")
    return (await posts_out([updated]))[0]


# Any logged-in member can edit any comment; there is deliberately no author check here.
@app.patch("/api/posts/{post_id}/comments/{comment_id}", response_model=Post)
async def update_comment(post_id: str, comment_id: str, body: CommentIn, me: CurrentUser) -> Post:
    return await edit_comment(post_id, comment_id, body.text, me, author_only=False)


# Only the member who wrote the comment can edit it.
@app.patch("/api/posts/{post_id}/comments/{comment_id}/own", response_model=Post)
async def update_own_comment(
    post_id: str, comment_id: str, body: CommentIn, me: CurrentUser
) -> Post:
    return await edit_comment(post_id, comment_id, body.text, me, author_only=True)
