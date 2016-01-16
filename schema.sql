drop table if exists user;
create table user (
  user_id integer primary key autoincrement,
  username text not null,
  pw_hash text not null,
  creation_time integer
);

drop table if exists review;
create table review (
  review_id integer primary key autoincrement,
  paper_id_raw integer not null,
  paper_id integer not null,
  author_id integer not null,
  text text not null,
  creation_time integer,
  update_time integer
);
