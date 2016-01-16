drop table if exists user;
create table user (
  user_id integer primary key autoincrement,
  username text not null,
  pw_hash text not null
);

