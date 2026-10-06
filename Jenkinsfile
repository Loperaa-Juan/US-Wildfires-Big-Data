// CI pipeline: for every pull request into main, install the locked dependencies, lint and run
// the tests. Jenkins runs these steps with uv (installed in jenkins/Dockerfile); no Maven is
// involved because this is a Python project.
//
// The Jenkins job is a Multibranch Pipeline that only discovers pull requests, so pushes to a
// branch do not start a build. When a new pull request or a new commit on an open pull request is
// found depends on the job: a periodic repository scan, or a GitHub webhook.
pipeline {
    agent any

    options {
        timeout(time: 15, unit: 'MINUTES')
        disableConcurrentBuilds()
    }

    stages {
        // Pull requests into other branches are discovered too; only those into main are tested
        stage('CI') {
            when {
                changeRequest target: 'main'
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
    }

    post {
        always {
            // Shows the test results (passed/failed per test) on the build page
            junit allowEmptyResults: true, testResults: 'reports/junit.xml'
        }
    }
}
