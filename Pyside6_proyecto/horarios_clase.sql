-- Horario semanal de clases por profesor (cuatrimestre y carrera). Correr una vez en el SQL Editor de Supabase.
create table if not exists horarios_clase (
    id bigint generated always as identity primary key,
    maestro_id uuid not null references maestros(id) on delete cascade,
    carrera text not null,
    periodo text not null,
    dia smallint not null check (dia between 1 and 5),   -- 1 = lunes ... 5 = viernes
    hora_inicio time not null,
    hora_fin time not null,
    tipo text not null check (tipo in ('clase', 'apoyo')),  -- apoyo = tutoria, asesorias, gestion del curso, etc.
    grupo text,
    materia text not null,
    nota text,                                              -- ej. "Entrada 8:30 hrs."
    creado_en timestamptz not null default now()
);

create index if not exists horarios_clase_maestro_idx on horarios_clase (maestro_id);

grant select, insert, update, delete on horarios_clase to anon, authenticated;
grant usage, select on all sequences in schema public to anon, authenticated;

alter table horarios_clase enable row level security;

do $$
begin
    if not exists (
        select 1 from pg_policies
        where schemaname = 'public' and tablename = 'horarios_clase' and policyname = 'app_acceso_total'
    ) then
        execute 'create policy app_acceso_total on horarios_clase for all to anon, authenticated using (true) with check (true)';
    end if;
end $$;
