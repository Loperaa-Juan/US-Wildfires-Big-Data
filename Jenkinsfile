// CI/CD pipeline, run by a Multibranch Pipeline job that discovers main and the pull requests
// (see jenkins/JENKINS.md). Python stages use uv; Docker stages use the host's Docker through its
// socket (jenkins/Dockerfile). No Maven is involved because this is a Python project.
//
// - Pull request into main: Install → Lint → Test.
// - main (every merge or push to it): the same, then
//   Build images → Start services (staging) → API tests → Deploy.
//
// Stages run in order and the build stops at the first failure, so the deploy only happens when
// every test before it passed.

import groovy.transform.Field

// Staging: a copy of the stack with no published ports (jenkins/docker-compose.staging.yml)
@Field String STAGING = 'wildfires-staging'
@Field String STAGING_COMPOSE = "docker compose -p ${STAGING} -f docker-compose.yml -f jenkins/docker-compose.staging.yml"
// Deployed stack: docker-compose.yml as it is, API on http://localhost:5000
@Field String PRODUCTION_COMPOSE = 'docker compose -p wildfires'

// Removes the staging containers. Volumes are kept, so the next build reuses the loaded MongoDB
def stopStaging() {
    sh """
        docker network disconnect ${STAGING}_default "\$(hostname)" 2>/dev/null || true
        ${STAGING_COMPOSE} down
    """
}

pipeline {
    agent any

    options {
        // The first build of main processes the whole dataset twice (staging and deploy);
        // later builds skip what is already done
        timeout(time: 3, unit: 'HOURS')
        disableConcurrentBuilds()
    }

    stages {
        stage('CI') {
            when {
                anyOf {
                    branch 'main'
                    changeRequest target: 'main'
                }
            }
            stages {
                stage('Install') {
                    steps {
                        sh 'uv sync --locked'
                    }
                }
                stage('Lint') {
                    steps {
                        sh 'uv run ruff check .'
                    }
                }
                stage('Test') {
                    steps {
                        sh 'uv run pytest --junitxml=reports/junit.xml'
                    }
                }
            }
        }

        stage('CD') {
            when {
                branch 'main'
            }
            stages {
                stage('Build images') {
                    steps {
                        // One service per image: etl builds us-wildfires-big-data (also used by
                        // Dask and the API), spark builds us-wildfires-big-data-spark (also used
                        // by the Spark master and workers). Building every service would build
                        // each image several times in parallel, and those builds collide
                        sh 'docker compose build etl spark'
                    }
                }
                stage('Start services') {
                    steps {
                        // The ETL downloads the dataset from Kaggle. The token is a Jenkins
                        // credential (ID `kaggle`, Username with password), exposed only to the
                        // commands inside the block and masked in the console output
                        withCredentials([usernamePassword(credentialsId: 'kaggle',
                                usernameVariable: 'KAGGLE_USERNAME', passwordVariable: 'KAGGLE_KEY')]) {
                            // Waits until the ETL and Spark stages finished and the API is healthy
                            sh "${STAGING_COMPOSE} up -d --wait"
                        }
                    }
                }
                stage('API tests') {
                    steps {
                        // Jenkins joins the staging network to call the API by its service name
                        sh """
                            docker network disconnect ${STAGING}_default "\$(hostname)" 2>/dev/null || true
                            docker network connect ${STAGING}_default "\$(hostname)"
                        """
                        sh 'jenkins/api-tests.sh http://api:5000'
                    }
                }
                stage('Deploy') {
                    steps {
                        script {
                            stopStaging()
                        }
                        withCredentials([usernamePassword(credentialsId: 'kaggle',
                                usernameVariable: 'KAGGLE_USERNAME', passwordVariable: 'KAGGLE_KEY')]) {
                            // Recreates only the containers whose image or configuration changed
                            sh "${PRODUCTION_COMPOSE} up -d --wait"
                        }
                        sh "${PRODUCTION_COMPOSE} ps"
                    }
                }
            }
        }
    }

    post {
        always {
            // Shows the test results (passed/failed per test) on the build page
            junit allowEmptyResults: true, testResults: 'reports/junit.xml'
        }
        unsuccessful {
            script {
                if (env.BRANCH_NAME == 'main') {
                    // Last log lines of the staging stack, to see from the build page what failed
                    sh "${STAGING_COMPOSE} logs --no-color --tail 100 || true"
                }
            }
        }
        cleanup {
            script {
                if (env.BRANCH_NAME == 'main') {
                    stopStaging()
                }
            }
        }
    }
}
