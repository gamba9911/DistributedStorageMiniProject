CREATE TABLE `file` (
   `id` INTEGER PRIMARY KEY AUTOINCREMENT,
   `filename` TEXT,
   `size` INTEGER,
   `content_type` TEXT,
   `part1_filenames` TEXT ,
   `part2_filenames` TEXT ,
   `part3_filenames` TEXT ,
   `part4_filenames` TEXT ,
   `created` DATETIME DEFAULT CURRENT_TIMESTAMP
);