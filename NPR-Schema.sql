CREATE TABLE article (
  id integer PRIMARY KEY NOT NULL,
  title varchar(255) NOT NULL,
  url varchar(255) NOT NULL,
  date datetime NOT NULL,
  file_url varchar(255) NOT NULL,
  program varchar(255),
  local_file varchar(255),
  duration integer NOT NULL DEFAULT(0)
);

CREATE UNIQUE INDEX unique_file ON article (file_url ASC);

CREATE UNIQUE INDEX unique_url ON article (url ASC);

CREATE TABLE podcast (
  pid integer PRIMARY KEY NOT NULL,
  title varchar(255) NOT NULL,
  description text,
  url varchar(255) NOT NULL,
  date text(128) NOT NULL,
  pub_date text NOT NULL,
  length char(128) NOT NULL,
  type char(128),
  duration char(128)
);