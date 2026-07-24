-- Image Storage Demo -- MySQL 8 schema
-- Apply with: mysql -u image_demo_user -p image_storage_demo < database/schema.sql
-- (Flask-Migrate manages this schema in normal operation; this file is
-- provided so the raw schema can be inspected/applied independently, e.g.
-- for the presentation's ERD or a from-scratch manual setup.)

CREATE DATABASE IF NOT EXISTS image_storage_demo
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE image_storage_demo;

CREATE TABLE IF NOT EXISTS images (
  id                  BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  filename            VARCHAR(255) NOT NULL,
  original_filename   VARCHAR(255) NOT NULL,
  mime_type           VARCHAR(100) NOT NULL,
  extension           VARCHAR(20)  NOT NULL,
  filesize            BIGINT UNSIGNED NOT NULL,
  storage_method      ENUM('filesystem', 'blob') NOT NULL,
  filepath            VARCHAR(500) NULL,
  upload_time         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  upload_duration_ms          DOUBLE NULL,
  last_retrieval_duration_ms  DOUBLE NULL,
  PRIMARY KEY (id),
  KEY idx_images_storage_method (storage_method),
  KEY idx_images_upload_time (upload_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS image_blobs (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  image_id    BIGINT UNSIGNED NOT NULL,
  image_data  LONGBLOB NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_image_blobs_image_id (image_id),
  CONSTRAINT fk_image_blobs_image
    FOREIGN KEY (image_id) REFERENCES images (id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
