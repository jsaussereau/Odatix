// ******************************
//           PARAMETERS
// ******************************
ThisBuild / scalaVersion     := "2.13.10"
ThisBuild / version          := "0.1.0"
ThisBuild / organization     := "IMS Laboratory"
val chiselVersion = "5.0.0"

val libDep = Seq(
  "org.chipsalliance" %% "chisel" % chiselVersion,
  "edu.berkeley.cs" %% "chiseltest" % "5.0.0" % "test"
)

val scalacOpt = Seq(
  "-language:reflectiveCalls",
  "-deprecation",
  "-feature",
  "-Xcheckinit",
  "-Ymacro-annotations"
)

// ******************************
//           PROJECTS
// ******************************
lazy val main = (project in file("."))
  .settings(
    name := "main",
    libraryDependencies ++= libDep,
    scalacOptions ++= scalacOpt,
    addCompilerPlugin("org.chipsalliance" % "chisel-plugin" % chiselVersion cross CrossVersion.full)
  )
