"""crear_tablas_iniciales

Revision ID: 23f57afc987c
Revises: 
Create Date: 2026-09-08 18:23:13.455553

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '23f57afc987c'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
     # 1. Tabla autores
    op.create_table(
        "autores",
        sa.Column("id_autor", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nombre_autor", sa.Text(), nullable=False),
        sa.Column("es_docente", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id_autor"),
    )

    # 2. Tabla mensajes
    op.create_table(
        "mensajes",
        sa.Column("id_mensaje", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id_mensaje_discord", sa.BigInteger(), nullable=False),
        sa.Column("autor_id", sa.Integer(), nullable=False),
        sa.Column("fecha_mensaje", sa.TIMESTAMP(), nullable=False),
        sa.Column("contenido", sa.Text(), nullable=False),
        sa.Column("es_pregunta", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.Column("origen", sa.Text()),
        sa.ForeignKeyConstraint(
            ["autor_id"],
            ["autores.id_autor"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id_mensaje"),
    )

    # 3. Tabla adjuntos
    op.create_table(
        "adjuntos",
        sa.Column("id_adjunto", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("mensaje_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("tipo", sa.Text()),
        sa.ForeignKeyConstraint(
            ["mensaje_id"],
            ["mensajes.id_mensaje"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id_adjunto"),
    )

    # 4. Tabla preguntas
    op.create_table(
        "preguntas",
        sa.Column("id_pregunta", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("mensaje_id", sa.Integer(), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("esta_cerrada", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.Column("sin_contexto", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.Column("es_administrativa", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.ForeignKeyConstraint(
            ["mensaje_id"],
            ["mensajes.id_mensaje"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id_pregunta"),
    )

    # 5. Tabla respuestas
    op.create_table(
        "respuestas",
        sa.Column("id_respuesta", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("mensaje_id", sa.Integer(), nullable=False),
        sa.Column("pregunta_id", sa.Integer(), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("es_validada", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.Column("es_corta", sa.Boolean(), server_default=sa.text("FALSE")),
        sa.ForeignKeyConstraint(
            ["mensaje_id"],
            ["mensajes.id_mensaje"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pregunta_id"],
            ["preguntas.id_pregunta"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id_respuesta"),
    )


def downgrade() -> None:
    op.drop_table("respuestas")
    op.drop_table("preguntas")
    op.drop_table("adjuntos")
    op.drop_table("mensajes")
    op.drop_table("autores")    

