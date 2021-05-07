provider "aws" {
  profile = var.profile
  region  = var.region
  version = "~> 3.39.0"
}

output "s3-bucket-name-radolan" {
  value = "${aws_s3_bucket.radolan.bucket_domain_name}"
}
resource "aws_s3_bucket" "radolan" {
  bucket        = "${var.prefix}-${var.name}-${var.env}"
  acl           = "public-read"
  force_destroy = true
  versioning {
    enabled = false
  }

  # Should be added for production
  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["PUT", "POST", "GET"]
    allowed_origins = var.allowed_origins
    expose_headers  = ["ETag"]
    max_age_seconds = 6000
  }

  tags = {
    name    = "terraform bucket for uploads from radolan recent module"
    project = "flsshygn"
    type    = "storage"
  }

}
