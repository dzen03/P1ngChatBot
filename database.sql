drop table if exists "user";
create table "user"(
    id bigint primary key);


drop table if exists chat;
create table chat(
    id bigint primary key);


drop table if exists dnd;
create table dnd(
    id serial primary key,
    user_id bigint references "user"(id),
    chat_id bigint references chat(id),
    start time with time zone not null default current_time,
    "end" time with time zone not null);


drop table if exists day_of_the_week;
create table day_of_the_week(
    id smallserial primary key); -- 1-7 <=> Mon.-Sun.

DO -- insert all days from 1 (Mon) to 7 (Sun)
$do$
BEGIN
    FOR i IN 1..7 LOOP
        insert into day_of_the_week (id) values (i);
    END LOOP;
END
$do$;


drop table if exists dnd_day;
create table dnd_day(
    dnd_id int references dnd(id),
    day_id int references day_of_the_week(id),
    PRIMARY KEY (dnd_id, day_id));


drop table if exists ping;
create table ping(
    id serial primary key,
    chat_id bigint references chat(id),
    alias text not null,
    unique (chat_id, alias));


drop table if exists ping_user;
create table ping_user(
    ping_id int references ping(id),
    user_id bigint references "user"(id),
    PRIMARY KEY (ping_id, user_id));
