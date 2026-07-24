-- Image Storage Demo -- illustrative seed data
-- Apply after schema.sql with: mysql -u image_demo_user -p image_storage_demo < database/seed.sql
--
-- These rows exist purely so the Gallery/Statistics/Comparison pages have
-- something to render immediately after a fresh install, before a
-- presenter uploads real images live.

USE image_storage_demo;

-- Filesystem-style row. NOTE: this references a filename that will not
-- actually exist on disk until a real file is uploaded through
-- /upload/filesystem -- it demonstrates the metadata shape only. Streaming
-- it via /image/filesystem/<id> will 404 until a matching file is placed
-- in uploads/ (or the row is replaced by a real upload).
INSERT INTO images
  (filename, original_filename, mime_type, extension, filesize,
   storage_method, filepath, upload_time)
VALUES
  ('00000000000000000000000000000001.png', 'sample-filesystem-demo.png',
   'image/png', 'png', 68, 'filesystem', 'uploads/00000000000000000000000000000001.png',
   NOW());

-- Database BLOB row using a genuine, valid 1x1 transparent GIF (34 bytes)
-- so /image/blob/<id> actually streams a real image out of the box.
INSERT INTO images
  (filename, original_filename, mime_type, extension, filesize,
   storage_method, filepath, upload_time)
VALUES
  ('00000000000000000000000000000002.gif', 'sample-blob-demo.gif',
   'image/gif', 'gif', 34, 'blob', NULL, NOW());

INSERT INTO image_blobs (image_id, image_data)
VALUES (
  LAST_INSERT_ID(),
  UNHEX('47494638396101000100800000000000ffffff2c00000000010001000002014c003b')
);
