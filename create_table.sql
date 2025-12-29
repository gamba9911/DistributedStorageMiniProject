CREATE TABLE `file` (
   `id` INTEGER PRIMARY KEY AUTOINCREMENT,
   `filename` TEXT,
   `size` INTEGER,
   `content_type` TEXT,
   `part1_filenames` TEXT ,
   `part2_filenames` TEXT ,
   `part3_filenames` TEXT ,
   `part4_filenames` TEXT ,
   `part1_nodes` TEXT,  
   `part2_nodes` TEXT,
   `part3_nodes` TEXT,
   `part4_nodes` TEXT,
   `created` DATETIME DEFAULT CURRENT_TIMESTAMP
);