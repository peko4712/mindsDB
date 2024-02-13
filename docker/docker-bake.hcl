# The default targets to be built if none are specified
group "default" {
  targets = ["bare", "devel", "cloud", "lightwood", "huggingface"]
}

variable "PUSH_TO_DOCKERHUB" {
  default = false
}
variable "IMAGE" {
  default = "mindsdb"
}
# This is a semver for releases but otherwise is a github sha
variable "VERSION" {
  default = "unknown"
}
variable "PLATFORMS" {
  default = ["linux/amd64", "linux/arm64"]
}

# Generate the list of tags for a given image.
# e.g. for the 'cloud' images this generates:
# - "mindsdb:cloud"        - This functions as a 'latest' tag for the cloud image
# - "mindsdb:v1.2.3-cloud" - For this specific version
# The same tags are pushed to dockerhub as well if the PUSH_TO_DOCKERHUB variable is set.
function "get_tags" {
  params = [target]
  result = [
    "454861456664.dkr.ecr.us-east-2.amazonaws.com/${IMAGE}:${VERSION}${notequal(target, "bare") ? "-${target}" : ""}",
    "454861456664.dkr.ecr.us-east-2.amazonaws.com/${IMAGE}:${notequal(target, "bare") ? target : "latest"}",
    PUSH_TO_DOCKERHUB ? "mindsdb/${IMAGE}:${VERSION}${notequal(target, "bare") ? "-${target}" : ""}" : "",
    PUSH_TO_DOCKERHUB ? "mindsdb/${IMAGE}:${notequal(target, "bare") ? target : "latest"}" : ""
  ]
} 



### OUTPUT IMAGES ###

target "images" {
  name = item.name
  dockerfile = "docker/mindsdb.Dockerfile" # If you change this, also change it in target:builder
  platforms = PLATFORMS
  matrix = {
    item = [
      {
        name = "bare"
        extras = ""
        target = ""
      },
      {
        name = "devel"
        extras = ""
        target = "dev"
      },
      {
        name = "lightwood"
        extras = ".[lightwood]"
        target = ""
      },
      {
        name = "huggingface"
        extras = ".[huggingface]"
        target = ""
      },
      {
        name = "cloud"
        extras = ".[lightwood,huggingface,statsforecast-extra,neuralforecast-extra,timegpt,surrealdb,mssql,youtube,ignite,gmail,pgvector,llama_index,writer,rag,github,snowflake,clickhouse] darts datasetsforecast"
        target = ""
      },

    ]
  }
  target = item.target
  tags = get_tags(item.name)
  args = {
    EXTRAS = item.extras
  }
}

