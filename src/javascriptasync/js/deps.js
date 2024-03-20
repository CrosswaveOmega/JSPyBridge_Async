const cp = require('child_process');
const fs = require('fs');
const {join} = require('path');
const {pathToFileURL} = require('url');

const NODE_PM = process.env.NODE_PM || 'npm';
const PACKAGE_PATH = join(__dirname, 'package.json');
const LOCK_PATH = join(
    __dirname, NODE_PM === 'npm' ? 'package-lock.json' : 'yarn.lock',
);
const MOD_PATH = join(__dirname, 'node_modules');
// console.log('mypath', process.env.NODE_PATH);
// process.env.NODE_PATH = join(__dirname, 'node_modules');
// console.log('mypath', process.env.NODE_PATH);
const log = (...what) => console.log('\x1b[1m', ...what, '\x1b[0m');

const defaultjson=`
'{
\t"name": "js-modules",
\t"description": "This folder holds the installed JS deps",
\t"dependencies": {}
}'
`;


/**
 * This class is responsible for the installation, storage,
 * and retrieval of JavaScript modules.
 *
 * @class
 * @classdesc Handles dependencies for the
 * application by providing methods for
 * saving, creating, updating the package.json file,
 * and installing JS packages into a specific NPM directory.
 */
class PackageManager {
  /**
   * Constructs a new PackageManager instance.
   */
  constructor() {
    this.loadedPackages = [];
  }

  /**
   * Attempts to re-load the installed packages from the package.json file.
   * In case of failure, creates a
   * default package.json file with basic attributes.
   */
  reload() {
    try {
      this.installed = JSON.parse(fs.readFileSync(PACKAGE_PATH));
    } catch (e) {
      fs.writeFileSync(PACKAGE_PATH,
          defaultjson);
      this.installed = JSON.parse(fs.readFileSync(PACKAGE_PATH));
    }
  }

  /**
   * Saves the installed package list to the package.json file.
   */
  save() {
    fs.writeFileSync(PACKAGE_PATH, JSON.stringify(this.installed, null, 2));
  }

  /**
   * Removes the package file and the lock file.
   */
  reset() {
    fs.rmSync(PACKAGE_PATH, {force: true});
    fs.rmSync(LOCK_PATH, {force: true});
    // This is unsafe:
    // fs.rmSync(MOD_PATH, { force: true, recursive: true })
  }

  /**
   * Retrieves the installed version of a given package.
   *
   * @param {string} name - Name of the package.
   * @return {string} - The installed version of the package.
   */
  getInstalledVersion(name) {
    return this.installed.dependencies[name];
  }

  /**
   * Sets the installed version of a given package
   *  and updates the package.json file.
   *
   * @param {string} name - Name of the package.
   * @param {string} version - Version of the package.
   */
  setInstalledVersion(name, version) {
    this.reload();
    this.installed.dependencies[name] = version;
    this.save();
  }

  /**
   * Installs a JavaScript package into the internal NPM module directory.
   * If a version is specified, then it uses that to form a new internal name
   * for this package to allow for having multiple versions
   * of the same package installed.
   *
   * @param {string} name - Name of the package to install.
   * @param {string} [version='latest'] - Version of the package to install.
   * @return {string} New internal package name.
   */
  install(name, version) {
    version = version || 'latest';
    this.reload();
    let internalName = name;
    if (version !== 'latest') {
      internalName = name + '--' + Buffer.from(version).toString('hex');
    }
    const installedVersion = this.getInstalledVersion(internalName);
    let needsInstall = false;
    if (version === 'latest' && installedVersion !== 'latest') {
      needsInstall = true;
    } else if (version !== 'latest' && !installedVersion) {
      needsInstall = true;
    }

    if (needsInstall) {
      log(
          `Installing '${name}' version '${version}'...'`+
      `This will only happen once.`,
      );
      if (version === 'latest') {
        // If version is latest, we need to handle this a bit differently.
        // `npm i package@latest` does NOT work, since it will not
        // actually save that into the Package Lock/JSON file. So we must first
        // put `latest` into the package.json, then run npm install
        // to persist the `latest` version.
        this.setInstalledVersion(name, 'latest');
        cp.execSync(`${NODE_PM} install`, {stdio: 'inherit', cwd: __dirname});
      } else {
        cp.execSync(
            `${NODE_PM} install ${internalName}@npm:${name}@${version}`,
            {stdio: 'inherit', cwd: __dirname});
      }

      process.stderr.write('\n\n');
      process.stdout.write('\n');
      log('OK.');
      return this.resolve(internalName);
    } else {
      // The package is already installed.
      return internalName;
    }
  }

  /**
   * Resolves the URL to a given package.
   *
   * @param {string} packageName - Name of the package to resolve.
   * @return {string} - URL to the main entry point of the package.
   */
  resolve(packageName) {
    const modPath = join(MOD_PATH, packageName);
    const packageInfo = require(join(modPath, 'package.json'));
    if (packageInfo.main) {
      let pname = join(modPath, packageInfo.main);
      // The ES6 `import()` function requires a file extension, always
      if (!packageInfo.main.endsWith('.js')) {
        try {
          const finfo = fs.lstatSync(pname);
          if (finfo.isDirectory()) pname = join(pname, '/index.js');
        } catch {
          pname += '.js';
        }
      }
      return pathToFileURL(pname);
    }
    // eslint-disable-next-line new-cap
    return new pathToFileURL(join(modPath, 'index.js'));
  }
}

const pm = new PackageManager();

/**
 * Asynchronously requires the provided module based on the name,
 * version and the relative path. If the relative path is provided,
 * it will attempt to load the module from the specified location.
 * If no version is specified, it defaults to the installed version.
 * If a version is specified, it will try to load the module from
 * the specific version.
 *
 * @async
 * @param {string} name - The name of the module to be required.
 * @param {string} version - The version of the module to be required.
 * @param {string} relativeTo - The path relative to which the module
 *                               needs to be required.
 * @return {Object|null} The required module.
 */
async function $require(name, version, relativeTo) {
  if (relativeTo) {
    // process.env.NODE_PATH= MOD_PATH;
    const mod = await import('file://' + join(relativeTo, name));
    return mod.default ?? mod;
  }

  if (!version) {
    // The user didn't specify a version. So try
    // whatever version we find installed. This can fail for non CJS modules.
    try {
      return require(name);
    } catch { }
  }

  // A version was specified, or the package wasn't found already installed.
  const newpath = pm.install(name, version);
  const mod = await import(newpath);
  return mod.default ?? mod;
}

/**
 * A simple Async Queue
 */
class AsyncQueue {
  /**
   * Constructs a new AsyncQueue instance.
   */
  constructor() {
    /** @private */
    this.queue = [];
  }

  /**
   * Enqueues an item into the queue.
   * @param {*} item The item to enqueue.
   */
  enqueue(item) {
    this.queue.push(item);
  }

  /**
   * Dequeues an item from the queue asynchronously.
   * @return {*} item the dequeued item,
   * or undefined if the queue is empty.
   */
  dequeue() {
    if (this.queue.length === 0) {
      return; // If the queue is empty, return nothing
    }
    return this.queue.shift();
  }
  /**
   * Peek the first element in the queue.
   * @return {*} the first item,
   * or undefined if the queue is empty.
   */
  peek() {
    if (this.queue.length === 0) {
      return; // If the queue is empty, return nothing
    }
    return this.queue[0];
  }

  /**
   * Checks if the queue has elements.
   * @return {boolean} True if the queue has elements, false otherwise.
   */
  hasElements() {
    return this.queue.length > 0;
  }
}

module.exports = {$require, AsyncQueue};

// async function test () {
//   console.log(await $require('prismarine-block'))
//   console.log(await $require('nbt'))
//   console.log(await $require('chalk', '2'))
//   console.log(await $require('chalk', '3'))
// }
// test()
//
