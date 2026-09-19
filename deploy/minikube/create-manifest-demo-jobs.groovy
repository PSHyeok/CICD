import hudson.model.ParametersDefinitionProperty
import hudson.model.StringParameterDefinition
import hudson.tasks.Shell
import hudson.model.FreeStyleProject
import jenkins.model.Jenkins

def jenkins = Jenkins.get()
def parameterNames = [
  'HOOK_EVENT_ID',
  'HOOK_SOURCE',
  'HOOK_BRANCH',
  'HOOK_SOURCE_BRANCH',
  'HOOK_TARGET_BRANCH',
  'HOOK_PULL_REQUEST',
  'HOOK_REVISION',
  'HOOK_REPOSITORIES',
  'ROUTING_MANIFEST_VERSION',
  'BUILD_TARGET',
]

['manifest-source', 'manifest-common'].each { jobName ->
  def job = jenkins.getItem(jobName)
  if (job == null) {
    job = jenkins.createProject(FreeStyleProject, jobName)
  }
  job.removeProperty(ParametersDefinitionProperty)
  def definitions = parameterNames.collect { name ->
    new StringParameterDefinition(name, '', 'CI/CD Hook Router parameter')
  }
  job.addProperty(new ParametersDefinitionProperty(definitions))
  job.getBuildersList().clear()
  job.getBuildersList().add(new Shell('''#!/bin/sh
set -eu
echo "manifest=$ROUTING_MANIFEST_VERSION"
echo "target=$BUILD_TARGET"
echo "repository=$HOOK_REPOSITORIES"
echo "source_branch=$HOOK_SOURCE_BRANCH"
echo "target_branch=$HOOK_TARGET_BRANCH"
echo "pull_request=$HOOK_PULL_REQUEST"
'''))
  job.save()
}

jenkins.save()
